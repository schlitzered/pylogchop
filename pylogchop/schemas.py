__author__ = 'schlitzer'


CHECK_CONFIG_MAIN = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "dlog_file",
    ],
    "properties": {
        "dlog_file": {
            "type": "string",
        },
        "include": {
            "type": "string",
        },
        "max_length": {
            "type": "integer",
        }
    }
}

CHECK_CONFIG_LOGGING = {}
CHECK_CONFIG_LOGGING['file:logging'] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "file",
        "retention",
        "level"
    ],
    "properties": {
        "file": {
            "type": "string"
        },
        "retention": {
            "type": "integer",
        },
        "level": {
            "type": "string",
            "enum": [
                "CRITICAL",
                "ERROR",
                "WARNING",
                "INFO",
                "DEBUG"
            ]
        },
    }
}
CHECK_CONFIG_LOGGING['syslog:logging'] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "address",
        "level"
    ],
    "properties": {
        "address": {
            "type": "string"
        },
        "syslog_facility": {
            "type": "string",
            "enum": [
                "auth",
                "authpriv",
                "cron",
                "daemon",
                "ftp",
                "kern",
                "lpr",
                "mail",
                "news",
                "syslog",
                "user",
                "uucp",
                "local0",
                "local1",
                "local2",
                "local3",
                "local4",
                "local5",
                "local6",
                "local7"
            ]
        },
        "level": {
            "type": "string",
            "enum": [
                "CRITICAL",
                "ERROR",
                "WARNING",
                "INFO",
                "DEBUG"
            ]
        },
    }
}

CHECK_CONFIG_SOURCE = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "syslog_facility",
        "syslog_tag",
        "syslog_severity",
        "tags",
        "template",
        "regex"
    ],
    "optional": [
        "encoding"
    ],
    "properties": {
        "encoding": {
            "type": "string",
        },
        "syslog_facility": {
            "type": "string",
            "enum": [
                "LOG_KERN",
                "LOG_USER",
                "LOG_MAIL",
                "LOG_DAEMON",
                "LOG_AUTH",
                "LOG_LPR",
                "LOG_NEWS",
                "LOG_UUCP",
                "LOG_CRON",
                "LOG_SYSLOG",
                "LOG_LOCAL0",
                "LOG_LOCAL1",
                "LOG_LOCAL2",
                "LOG_LOCAL3",
                "LOG_LOCAL4",
                "LOG_LOCAL5",
                "LOG_LOCAL6",
                "LOG_LOCAL7"
            ]
        },
        "syslog_tag": {
            "type": "string",
        },
        "syslog_severity": {
            "type": "string",
            "enum": [
                "LOG_EMERG",
                "LOG_ALERT",
                "LOG_CRIT",
                "LOG_ERR",
                "LOG_WARNING",
                "LOG_NOTICE",
                "LOG_INFO",
                "LOG_DEBUG",
            ]
        },
        "tags": {
            "type": "string",
        },
        "template": {
            "type": "string",
        },
        "regex": {
            "type": "string",
        },
    }
}
