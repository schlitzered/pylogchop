__author__ = 'schlitzer'
# stdlib
import copy
import json
import json.decoder
import logging
import os
import re
import threading
import time


class Worker(threading.Thread):
    def __init__(
            self, file, msgqueue, tags, regex, template,
            syslog_facility, syslog_tag, syslog_severity,
    ):
        super().__init__(name='Worker:'+file)
        self.log = logging.getLogger('pylogchop')
        self._fd = None
        self._file = file
        self._data = None
        self._msgqueue = msgqueue
        self._st_ino = None
        self._st_dev = None
        self._st_size = None
        self._pos = None
        self._regex = None
        self._tags = None
        self._tags_dict = None
        self._template = None
        self.template = template
        self.regex = regex
        self.syslog_facility = syslog_facility
        self.syslog_tag = syslog_tag
        self.syslog_severity = syslog_severity
        self.tags = tags
        self.tags_dict = tags
        self.terminate = False

    @property
    def regex(self):
        return self._regex

    @regex.setter
    def regex(self, regex):
        if regex == '':
            self._regex = None
        else:
            self._regex = re.compile(regex)

    @property
    def template(self):
        return self._template

    @template.setter
    def template(self, template):
        try:
            with open(template, 'r') as f:
                try:
                    self._template = json.load(f)
                except json.decoder.JSONDecodeError as err:
                    self.log.fatal("could not parse template".format(err))
        except OSError as err:
            self.log.fatal("could not read template: {0}".format(err))

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, tags):
        self._tags = tags.split(',')
        self.tags_dict = tags

    @property
    def tags_dict(self):
        return self._tags_dict

    @tags_dict.setter
    def tags_dict(self, tags):
        tags_dict = {}
        tags = tags.split(',')
        for tag in tags:
            tag = tag.split(':', 1)
            if len(tag) != 2:
                self.log.error("cannot create k,v from tag {0}".format(tag))
                continue
            key, value = tag
            tags_dict[key] = value
        self._tags_dict = tags_dict

    def _build_message(self, msg):
        for key, value in msg.items():
            if isinstance(value, dict):
                self._build_message(msg[key])
            elif isinstance(value, str):
                if value == "$FIRST_LINE":
                    msg[key] = self._data['first_line']
                elif value == "$OTHER_LINES":
                    msg[key] = self._data['other_lines']
                elif value == "$TAGS":
                    msg[key] = self.tags
                elif value == "$TAGS_DICT":
                    msg[key] = self.tags_dict
                elif value.startswith('$RE_'):
                    value = value.split('_')
                    if not len(value) == 3:
                        continue
                    try:
                        grp_num = int(value[1])
                    except ValueError:
                        continue
                    grp_type = value[2]
                    if grp_type == u'INT':
                        try:
                            msg[key] = int(self._data['match'].group(grp_num))
                        except IndexError:
                            self.log.error("no match group {0}".format(grp_num))
                        except ValueError:
                            self.log.error("cannot transform {0} to integer".format(self._data['match'].group(grp_num)))
                    elif grp_type == u'FLOAT':
                        try:
                            msg[key] = float(self._data['match'].group(grp_num))
                        except IndexError:
                            self.log.error("no match group {0}".format(grp_num))
                        except ValueError:
                            self.log.error("cannot transform {0} to float".format(self._data['match'].group(grp_num)))
                    elif grp_type == u'STR':
                        try:
                            msg[key] = self._data['match'].group(grp_num)
                        except IndexError:
                            self.log.error("no match group {0}".format(grp_num))

    def build_message(self):
        msg = {
            "tag": self.syslog_tag,
            "severity": self.syslog_severity,
            "facility": self.syslog_facility
        }
        payload = copy.deepcopy(self.template)
        self._build_message(payload)
        msg["payload"] = payload
        self._msgqueue.append(msg)
        self._data = None

    def process_line(self, line):
        if self.regex:
            match = self.regex.match(line)
            if match and self._data:
                self.log.debug("submitting previous message")
                self.build_message()
                self.log.debug("detected new log message")
                self.process_first_line(line, match)
            elif match and not self._data:
                self.log.debug("detected new log message")
                self.process_first_line(line, match)
            elif self._data and not match:
                self.log.debug("got new line for multiline payload")
                self._data['other_lines'].append(line)
                self._data['starving'] = False
            else:
                self.log.error("got line that is not matching regex, and not part of a multiline log message")
                self.log.error("{0}".format(line))
                pass
        else:
            self.log.debug("got new plan log message")
            self.process_first_line(line, None)
            self.build_message()

    def process_first_line(self, line, match):
        self.log.debug("creating new message")
        self._data = {
            "starving": False,
            "facility": self.syslog_facility,
            "tag": self.syslog_tag,
            "severity": self.syslog_severity,
            "first_line":  line,
            "other_lines": [],
            "match": match
        }

    def close(self):
        if self._fd:
            self.log.debug("closing log file")
            self._fd.close()
            self._fd = None
            self.log.debug("done closing log file")

    def follow(self):
        while not self.terminate:
            if self._fd:
                self.chk_stat()
            if not self._fd:
                self.open()
            if not self._fd:
                continue
            self._pos = self._fd.tell()
            line = self._fd.readline()
            if line:
                yield line
            else:
                self._fd.seek(self._pos, 0)
                if self._data:
                    if self._data['starving']:
                        self.build_message()
                    else:
                        self._data['starving'] = True
                time.sleep(1)

    def chk_stat(self):
        try:
            stat = os.stat(self._file)
        except OSError as err:
            self.log.error("could not stat file: {0}".format(err))
            self.close()
            return
        if self._pos > stat.st_size:
            self.log.info("truncate detected, reopening")
            self.close()
        elif self._st_dev != stat.st_dev:
            self.log.info("underling device changed, reopening")
            self.close()
        elif self._st_ino != stat.st_ino:
            self.log.info("inode has changed, reopening")
            self.close()

    def _open(self):
        if self._fd:
            self.close()
        self.log.debug("open logfile")
        try:
            self._fd = open(self._file, 'r')
            self._fd.seek(0, 2)
            stat = os.stat(self._file)
            self._st_dev = stat.st_dev
            self._st_ino = stat.st_ino
            self._pos = self._fd.tell()
        except OSError as err:
            self.log.error("could not open logfile: {0}".format(err))
            return False
        self.log.debug("done open logfile")
        return True

    def open(self):
        sleep = 0
        while not self.terminate:
            if sleep == 0:
                if self._open():
                    return
                sleep = 10
                self.log.error("retrying opening in 10 seconds")
            else:
                time.sleep(1)
                sleep -= 1

    def run(self):
        self.log.info("i am up")
        for line in self.follow():
            if self.terminate:
                break
            self.process_line(line)
        self.log.info("i am going down")
        self.close()
        self.log.info("gone")
