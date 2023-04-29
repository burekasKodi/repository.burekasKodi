import inspect          # log filename and line number
import xbmc             # log api and levels
import xbmcaddon        # for addong settings (debug)
import os

__addon__ = xbmcaddon.Addon()
debug = __addon__.getSetting("Debug")

class logging:
    # def __init__(self):
    #     self.level = xbmc.LOGINFO # not used ...

    def getlogprefix(self):
        # going to older frame because the stack is:
        #   user func -> log.info() -> log -> getlogprefix()

        f = inspect.currentframe().f_back.f_back.f_back
        filepath =  inspect.getframeinfo(f).filename
        filename = os.path.basename(filepath)
        line = f.f_lineno
        return "#####[AllSubs]##### %s[%04d]: " % (filename, line)
    
    def log(self, msg, level):
        if not isinstance(msg, str):
            msg = repr(msg)

        prefix = self.getlogprefix()
        try:
            xbmc.log(prefix + msg, level)
        except UnicodeEncodeError:
            xbmc.log(prefix + msg.encode( "utf-8", "ignore" ), level)        

    # log with level debug, in case user set in settings debug it will log it
    # as info, this allows print debugs of our module without the need for the
    # all kodi debug system
    def debug(self, msg):
        level = xbmc.LOGDEBUG
        if "true" == debug:
            level = xbmc.LOGINFO

        self.log(msg, level)

    def info(self, msg):
        self.log(msg, xbmc.LOGINFO)

    def warning(self, msg):
        self.log(msg, xbmc.LOGWARNING)

    def error(self, msg):
        self.log(msg, xbmc.LOGERROR)

logger = logging()

def myLogger(msg, logLevel = xbmc.LOGDEBUG, force = False):     ##### burekas
    #logging.warning(msg)
    if(debug == "true" or force):
        if logLevel == xbmc.LOGDEBUG:
            logLevel = xbmc.LOGINFO #xbmc.LOGWARNING

    if not isinstance(msg, str):
        msg = repr(msg)

    try:
        xbmc.log("#####[AllSubs]##### " + msg, logLevel)
    except UnicodeEncodeError:
        xbmc.log("#####[AllSubs]##### " + msg.encode( "utf-8", "ignore" ), logLevel)
