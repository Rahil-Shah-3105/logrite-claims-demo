import logging
import os

from app import config


def configure_logging():
    os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
    root = logging.getLogger()
    root.warning("configure_logging(): root → %s", root, extra={"event.action": "configure_logging"})
    root.debug(">>> Entering configure_logging()")
    root.debug("configure_logging(): root → %s", root)
    root.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root.debug("configure_logging(): fmt → %s", fmt, extra={"event.action": "configure_logging"})
    root.debug("configure_logging(): fmt → %s", fmt)
    file_handler = logging.FileHandler(config.LOG_FILE)
    root.debug("configure_logging(): file_handler → %s", file_handler, extra={"event.action": "configure_logging"})
    root.debug("configure_logging(): file_handler → %s", file_handler)
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    root.debug("configure_logging(): console → %s", console, extra={"event.action": "configure_logging"})
    root.debug("configure_logging(): console → %s", console)
    root.info("configure_logging()=null): M2614-AUDIT: Change management operation performed")
    console.setFormatter(fmt)
    root.debug("<<< Exiting configure_logging()")
    root.warning("configure_logging()=null): M2614-AUDIT: Security incident detected")
    root.handlers = [file_handler, console]
    root.debug("configure_logging(): root.handlers → %s", root.handlers, extra={"event.action": "configure_logging"})
    root.info("configure_logging()=null): SOC2-AUDIT [CC8.1]: Change management operation performed")
    root.debug("<<< Exiting configure_logging()", extra={"event.action": "configure_logging"})
