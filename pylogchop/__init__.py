__author__ = 'schlitzer'
# stdlib
import argparse
import configparser
from collections import deque
import json
import os
import signal
import sys
import syslog
import time
import logging
from logging.handlers import TimedRotatingFileHandler

# 3rd party
import jsonschema
import jsonschema.exceptions
from pep3143daemon import DaemonContext, PidFile

# project
from pylogchop.schemas import *
from pylogchop.worker import Worker


def main():
    parser = argparse.ArgumentParser(description="PyLogChop ")

    parser.add_argument("--cfg", dest="cfg", action="store",
                        default="/etc/pylogchop/pylogchop.ini",
                        help="Full path to configuration")

    parser.add_argument("--pid", dest="pid", action="store",
                        default="/var/run/pylogchop.pid",
                        help="Full path to PID file")

    parser.add_argument("--nodaemon", dest="nodaemon", action="store_true",
                        help="Do not daemonize, run in foreground")

    subparsers = parser.add_subparsers(help='commands', dest='method')
    subparsers.required = True

    quit_parser = subparsers.add_parser('quit', help='Stop PyLogChop')
    quit_parser.set_defaults(method='quit')

    quit_parser = subparsers.add_parser('reload', help='Reload PyLogChop')
    quit_parser.set_defaults(method='reload')

    start_parser = subparsers.add_parser('start', help='Start PyLogChop')
    start_parser.set_defaults(method='start')

    parsed_args = parser.parse_args()

    if parsed_args.method == 'quit':
        pylogchopapi = PyLogChop(
            cfg=parsed_args.cfg,
            pid=parsed_args.pid,
            nodaemon=parsed_args.nodaemon
        )
        pylogchopapi.quit()

    elif parsed_args.method == 'reload':
        pylogchopapi = PyLogChop(
            cfg=parsed_args.cfg,
            pid=parsed_args.pid,
            nodaemon=parsed_args.nodaemon
        )
        pylogchopapi.reload()

    elif parsed_args.method == 'start':
        pylogchopapi = PyLogChop(
            cfg=parsed_args.cfg,
            pid=parsed_args.pid,
            nodaemon=parsed_args.nodaemon
        )
        pylogchopapi.start()


class PyLogChop(object):
    def __init__(self, cfg, pid, nodaemon):
        self._config_file = cfg
        self._config = configparser.ConfigParser()
        self._config_dict = None
        self._deque = deque()
        self._pid = pid
        self._nodaemon = nodaemon
        self._terminate = False
        self._worker = dict()
        self.log = logging.getLogger('pylogchop')

    def _app_logging(self):
        logfmt = logging.Formatter('%(asctime)sUTC - %(threadName)s - %(levelname)s - %(message)s')
        logfmt.converter = time.gmtime
        app_handlers = []
        aap_level = self.config.get('file:logging', 'level')
        app_log = self.config.get('file:logging', 'file')
        app_retention = self.config.getint('file:logging', 'retention')
        app_handlers.append(TimedRotatingFileHandler(app_log, 'd', app_retention))

        for handler in app_handlers:
            handler.setFormatter(logfmt)
            self.log.addHandler(handler)
        self.log.setLevel(aap_level)
        self.log.debug("file logger is up")

    def _process_message(self):
        try:
            msg = self._deque.popleft()
            tag = msg['tag']
            facility = msg['facility']
            severity = msg['severity']
            syslog.openlog(tag, 0, getattr(syslog, facility))
            syslog.syslog(getattr(syslog, severity), json.dumps(msg['payload']))
            syslog.closelog()
            return True
        except IndexError:
            time.sleep(0.1)
            return False

    def _run(self):
        if 'file:logging' in self._config_dict.keys():
            self._app_logging()
        self.log.info("starting up")
        for section in self._config_dict.keys():
            if section.endswith(':source'):
                self._worker_start(section)
        while not self._terminate:
            self._process_message()
        self.log.info("shutting down worker threads")
        for worker in self._worker.keys():
            self._worker_stop(worker)
        self.log.info("shutdown signal send to worker threads")
        self.log.info("waiting for worker threads to terminate")
        for worker in self._worker.keys():
            self._worker_join(worker)
        self.log.info("all worker threads gone")
        self.log.info("cleanup up message queue")
        while True:
            if not self._process_message():
                break
        self.log.info("successfully shutdown")

    def _reload(self, sig, frm):
        self.log.info("reloading configuration")
        try:
            cfg = configparser.ConfigParser()
            with open(self._config_file, 'r') as f:
                cfg.read_file(f)
            self._config = cfg
        except OSError as err:
            self.log.error("could not read configuration".format(err))
        self._config_dict = self._cfg_to_dict(self.config)
        for section in self._config_dict.keys():
            if section.endswith(':source'):
                if section in self._worker:
                    self._worker_reload(section)
                else:
                    self._worker_start(section)
        term = []
        for section in self._worker.keys():
            if section not in self._config_dict.keys():
                self._worker_stop(section)
                self._worker_join(section)
                term.append(section)
        for worker in term:
            self._worker.pop(worker)
        self.log.info("done reloading configuration")

    def _quit(self, sig, frm):
        self._terminate = True

    def _worker_cfg_ok(self, source):
        self.log.info("checking config for {0}".format(source))
        try:
            jsonschema.validate(self._config_dict[source], CHECK_CONFIG_SOURCE)
            self.log.info("done checking config for {0}".format(source))
            return True
        except jsonschema.exceptions.ValidationError as err:
            self.log.error("defect config for {0} \n{1}".format(source, err))

    def _worker_start(self, source):
        self.log.info("starting worker: {0}".format(source))
        if not self._worker_cfg_ok(source):
            self.log.error("skipping worker {0} because of broken configuration".format(source))
            return
        file = source.rstrip(':source')
        conf = self._config_dict[source]
        worker = Worker(
            file=file, msgqueue=self._deque,
            tags=conf['tags'],
            template=conf['template'],
            syslog_facility=conf['syslog_facility'],
            syslog_severity=conf['syslog_severity'],
            syslog_tag=conf['syslog_tag'],
            regex=conf['regex']
        )
        worker.start()
        self._worker[source] = worker
        self.log.info("worker: {0} running".format(source))

    def _worker_stop(self, source):
        self.log.info("sending termination signal for worker {0}".format(source))
        self._worker[source].terminate = True
        self.log.info("sent termination signal for worker {0}".format(source))

    def _worker_reload(self, source):
        self.log.info("reloading configuration for worker {0}".format(source))
        if not self._worker_cfg_ok(source):
            self.log.error("skipping worker {0} because of broken configuration".format(source))
            return
        conf = self._config_dict[source]
        worker = self._worker[source]
        worker.tags = conf['tags']
        worker.template = conf['template']
        worker.syslog_facility = conf['syslog_facility']
        worker.syslog_severity = conf['syslog_severity']
        worker.syslog_tag = conf['syslog_tag']
        worker.regex = conf['regex']
        self.log.info("done reloading configuration for worker {0}".format(source))

    def _worker_join(self, source):
        self.log.info("waiting for worker {0} to finish".format(source))
        self._worker[source].join()
        self.log.info("worker {0} stopped".format(source))

    @staticmethod
    def _cfg_to_dict(config):
        result = {}
        for section in config.sections():
            result[section] = {}
            for option in config.options(section):
                try:
                    result[section][option] = config.getint(section, option)
                    continue
                except ValueError:
                    pass
                try:
                    result[section][option] = config.getfloat(section, option)
                    continue
                except ValueError:
                    pass
                try:
                    result[section][option] = config.getboolean(section, option)
                    continue
                except ValueError:
                    pass
                try:
                    result[section][option] = config.get(section, option)
                    continue
                except ValueError:
                    pass
        return result

    @property
    def config(self):
        return self._config

    @property
    def config_dict(self):
        return self._config_dict

    @property
    def pid(self):
        return self._pid

    @property
    def nodaemon(self):
        return self._nodaemon

    def quit(self):
        try:
            pid = open(self.pid).readline()
        except IOError:
            print("Daemon already gone, or pidfile was deleted manually")
            sys.exit(1)
        print("terminating Daemon with Pid: {0}".format(pid))
        os.kill(int(pid), signal.SIGTERM)
        sys.stdout.write("Waiting...")
        while os.path.isfile(self.pid):
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(0.5)
        print("Gone")

    def reload(self):
        try:
            pid = open(self.pid).readline()
        except IOError:
            print("no pidfile found")
            sys.exit(1)
        try:
            os.kill(int(pid), signal.SIGHUP)
            print("reload command send")
            sys.exit(0)
        except OSError as err:
            print("could not send reload command, daemon gone")
            print(err)
            sys.exit(1)

    def start(self):
        with open(self._config_file, 'r') as f:
            self.config.read_file(f)
        self._config_dict = self._cfg_to_dict(self.config)
        try:
            jsonschema.validate(self.config_dict['main'], CHECK_CONFIG_MAIN)
        except jsonschema.exceptions.ValidationError as err:
            print("main section: {0}".format(err))
            sys.exit(1)
        daemon = DaemonContext(pidfile=PidFile(self.pid))
        if self.nodaemon:
            daemon.detach_process = False
        dlog = open(self.config.get('main', 'dlog_file'), 'w')
        daemon.stderr = dlog
        daemon.stdout = dlog
        daemon.open()
        signal.signal(signal.SIGHUP, self._reload)
        signal.signal(signal.SIGTERM, self._quit)
        self._run()
