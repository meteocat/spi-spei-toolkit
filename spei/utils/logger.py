"""Module to create a Logger with specific"""

import atexit
import inspect
import logging
import os
import socket
import time
from logging.handlers import QueueHandler, QueueListener, TimedRotatingFileHandler
from multiprocessing import Queue

_loggers = {}
_queue_listeners = {}
_log_queues = {}


class NumericTimedRotatingFileHandler(TimedRotatingFileHandler):

    def doRollover(self):
        """
        doRollover() with the rotation addapted from RotatingFileHandler,
        but starting from .log.0
        """
        # get the time that this sequence started at and make it a TimeTuple
        currentTime = int(time.time())
        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstNow = time.localtime(currentTime)[-1]
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                timeTuple = time.localtime(t + addend)

        if self.stream:
            self.stream.close()
            self.stream = None
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, -1, -1):
                sfn = self.rotation_filename("%s.%d" % (self.baseFilename, i))
                dfn = self.rotation_filename("%s.%d" % (self.baseFilename, i + 1))
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.rotation_filename(self.baseFilename + ".0")
            if os.path.exists(dfn):
                os.remove(dfn)
            self.rotate(self.baseFilename, dfn)
        if not self.delay:
            self.stream = self._open()
        self.rolloverAt = self.computeRollover(currentTime)


class ContextFilter(logging.Filter):
    hostname = socket.gethostname()

    def filter(self, record):
        record.hostname = ContextFilter.hostname
        if not hasattr(record, "pathname"):
            record.pathname = os.path.realpath(__file__)
        return True


def create_static_logger(log_file: str, log_name: str):
    """Create a logger.

    Args:
        log_file (str): Logger file path.
        log_name (str): Logger name.

    Returns:
        logging.Logger: Logger.
    """

    caller_frame = inspect.stack()[1]
    caller_file = caller_frame.filename

    logger = logging.getLogger(log_name)
    logger.setLevel(logging.DEBUG)
    str_hdl = logging.FileHandler(log_file)
    formatter = logging.Formatter(
        "%(asctime)s|%(hostname)s|" + caller_file + "|%(levelname)s|%(message)s",
        "%Y/%m/%d|%H:%M:%S",
    )
    str_hdl.addFilter(ContextFilter())
    str_hdl.setFormatter(formatter)
    logger.addHandler(str_hdl)
    logger.propagate = False

    return logger


def create_logger(
    log_file: str, log_name: str, when="midnight", interval=1, backup_count=8
):
    """
    Crea un logger amb rotació diària a les 00:00
    i còpies numerades:
        .log → .log.0 → .log.1 → ... fins a backup_count

    Args:
        log_file (str): Path del fitxer de log principal.
        log_name (str): Nom del logger.
        when (str): Quan es fa la rotació (per defecte midnight).
        interval (int): Interval de la rotació (per defecte 1).
        backup_count (int): Nombre de còpies (per defecte 8).
    """

    if log_name in _loggers:
        return _loggers[log_name]
    
    caller_file = inspect.stack()[1].filename

    logger = logging.getLogger(log_name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()  # Netejar handlers previs
    logger.propagate = False

    # Crear la cua
    _log_queues[log_name] = Queue(-1)


    handler = NumericTimedRotatingFileHandler(
        log_file,
        when=when,
        backupCount=backup_count,
        interval=interval,
        encoding="utf-8",
    )

    formatter = logging.Formatter(
        "%(asctime)s|%(hostname)s|" + caller_file + "|%(levelname)s|%(message)s",
        "%Y/%m/%d|%H:%M:%S",
    )

    handler.addFilter(ContextFilter())
    handler.setFormatter(formatter)

    # Crear listener que escriu des de la cua
    _queue_listener = QueueListener(
        _log_queues[log_name], handler, respect_handler_level=True
    )
    _queue_listener.start()

    _queue_listeners[log_name] = _queue_listener

    # Assegurar que el listener s'atura en sortir
    atexit.register(_queue_listener.stop)

    # Tots els processos (principal i fills) usen QueueHandler
    queue_handler = QueueHandler(_log_queues[log_name])
    logger.addHandler(queue_handler)
    
    # Register logger
    _loggers[log_name] = logger

    return logger


def stop_logger_listener():
    """Atura el listener de logs. Cridar això al final del programa principal."""
    
    for name, listener in list(_queue_listeners.items()):
        try:
            listener.stop()
        except Exception:
            pass
        _queue_listeners.clear()
    