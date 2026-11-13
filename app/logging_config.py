import logging
import os

from app import config


def configure_logging():
    os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
    root = logging.getLogger()
    root.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    root.warning("configure_logging(): root → %s", root, extra={"event.action": "configure_logging"})
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root.debug("configure_logging(): fmt → %s", fmt, extra={"event.action": "configure_logging"})
    file_handler = logging.FileHandler(config.LOG_FILE)
    file_handler.setFormatter(fmt)
    root.debug("configure_logging(): file_handler → %s", file_handler, extra={"event.action": "configure_logging"})
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.debug("configure_logging(): console → %s", console, extra={"event.action": "configure_logging"})
    root.handlers = [file_handler, console]
    root.debug("<<< Exiting configure_logging()", extra={"event.action": "configure_logging"})
    root.debug("configure_logging(): root.handlers → %s", root.handlers, extra={"event.action": "configure_logging"})
