'''
    scalalib.py - (C) 2005-2010 Scala, Guillaume Proux, Mike Miller
    A module to simplify using Scala from python, including a few extra
    helpful functions.  Send questions regarding this module to mike dot miller
    at scala dot com.

    Place in the lib/site-packages folder of your Scala for Python installation.

    The dictionary, persistent_data, may be used to carry information from
    script to script running under the same interpreter.
'''
if True:            # initialize, enable folding
    import sys, os, time
    import logging, logging.handlers
    try:                    from win32com.client import Dispatch as COMObject
    except ImportError:     print 'Warning: Windows support not available.'

    __version__ = '1.23'
    _def_logport = 8400
    _log = logging.getLogger(__name__)
    persistent_data = {}    # A place to keep information across scripts

    # Scala COM handles, initialized on demand
    _player  = None;    _player_name    = 'ScalaPlayer.ScalaPlayer.1'
    _runic   = None;    _runic_name     = 'Scala.InfoPlayer5'
    _netic   = None;    _netic_name     = 'Scala.InfoNetwork'
    _publshr = None;    _publshr_name   = 'Scala.Publisher'
    _thumbnl = None;    _thumbnl_name   = 'Scala.Thumbnailer'
    _filelock_name  = 'ScalaFileLock.ScalaFileLock.1'
    _netic_svc      = 'ScalaNetClient5'
    _pub_svc        = 'ScalaPublish5'
    _thumb_svc      = 'ScalaSupport5'
    sleep_was_successful = False


# Classes
# ---------------------------------------------------------------------
class sharedvars:   # from scala5
    '''
        A class to wrap Scala shared variables (WSH Objects), so using .Value
        isn't necessary to set/access their values.  Shared variables can be
        accessed as attributes of the resulting object.

        Argument:
            defaults                - A dictionary of default values to return.
        Additional behavior:
            - If attempting to read a variable that doesn't exist, or wasn't
                shared, this returns a default (if given), otherwise None.
            - Will silently drop assignments to variables that weren't shared.
            - The Scala vars continue to be available in the main namespace.
            - This version fixes the bug regarding one-element arrays not
                returning to the Scala Script.
        Notes:
            Use of this object is optional and not required to access Scala's
            shared variables.   However, its use makes it easier to write
            scripts that work at the command prompt as well, since scripts
            won't crash on variable access.

        Example:
            import scalalib
            svars = scalalib.sharedvars()  # a defaults dict can be passed here.
            f = file(svars.filename)       # get value
            svars.result = 15              # set value
    '''
    def __init__(self, defaults={}):
        self.__dict__['main'] = sys._getframe(1).f_globals
        self.__dict__['defaults'] = defaults

    def __getattr__(self, name):
        try:
            result = self.__dict__['main'][name].Value
            if type(result) is tuple:
                result = list(result)
            return result
        except KeyError:
            return self.defaults.get(name, None)

    def __setattr__(self, name, newval):
        try:
            svar = self.__dict__['main'][name]
            if type(newval) is list:
                if len(newval) == 1:    # to ensure new value sticks at len = 1
                    default = { str:'', int:0, float:0.0, bool:False
                        }[type(newval[0])]
                    newval = tuple(newval) + (default,)
                else:
                    newval = tuple(newval)
            svar.Value = newval
        except KeyError: pass           # drop assignments that don't apply


class _ObjectNotAvailable(Exception):
    '''Thrown when a Scala COM Object is unable to be instantiated.'''
    pass


class _ScalaLogHandler(logging.Handler):
    '''A class implementing the Scala logging system as a python logging
    handler.  Log messages are written to the Scala log.'''
    def emit(self, record):
        try:
            msg = self.format(record)
            _log_scala(msg)
        except:
            self.handleError(record)


class _ScalaVarHandler(logging.Handler):
    '''A class implementing a Scala variable as a python logging handler.
    Log messages are written to the named variable, and are available for
    viewing in Scala Player or Designer.'''
    def __init__(self, debug_var_name, level=logging.NOTSET):
        logging.Handler.__init__(self, level=level)
        self.dvn = debug_var_name
        self.frame = 0

    def emit(self, record):
        try:
            msg = self.format(record)
            # The frame (or stack) number can change depending on which function
            # we are calling from.  The first time, we look for the var in frame
            # 0.  If we fail, we search for it, and if found, continue to try
            # that one every time until we fail again.  Only searches if var is
            # not found, saving work when the fr# doesn't change (most likely).
            try: sys._getframe(self.frame).f_globals[self.dvn].Value = msg
            except KeyError:
                for i in range(10):     # Try to find the frame if we've lost it
                    try:
                        sys._getframe(i).f_globals[self.dvn]
                        self.frame = i; break
                    except KeyError: continue   # not in this frame
                    except ValueError: break    # too far
                    break                       # success
                # try again
                try: sys._getframe(self.frame).f_globals[self.dvn].Value = msg
                except KeyError: pass  # couldn't find it, skip this event
        except:
            self.handleError(record)


class _Win32ColorConHandler(logging.Handler):
    '''A class that adds color to the standard console StreamHandler.'''

    def __init__(self, level=logging.NOTSET):
        logging.Handler.__init__(self, level)
        import WConio
        self.WConio = WConio
        self.colormap = {'DEBUG': WConio.BLUE, 'INFO':WConio.GREEN,
            'WARNING':WConio.YELLOW, 'ERROR':WConio.LIGHTRED,
            'CRITICAL':WConio.WHITE, 'NOTSET':WConio.LIGHTGREY }

    def emit(self, record):
        WConio = self.WConio
        try:
            msg = self.format(record)
            levelname = record.levelname
            out = sys.__stdout__  # in case redirected by filelogger, etc
            if levelname in msg:
                part1, part2 = msg.split(levelname, 1)
                out.write(part1)
                out.flush()
                saved_color = WConio.gettextinfo()[4]
                WConio.textattr( self.colormap.get(levelname,
                    WConio.LIGHTGREY) )
                if levelname == 'CRITICAL':  WConio.textbackground(WConio.RED)
                WConio.cputs(levelname)
                WConio.textattr(saved_color)  # restore
                print >> out, part2
            else:
                print >> out, msg
            out.flush()
        except:
            self.handleError(record)


class _CursesConHandler(logging.Handler):
    '''A class that adds color to the standard console StreamHandler.'''

    def __init__(self, level=logging.NOTSET):
        logging.Handler.__init__(self, level)
        import curses
        curses.setupterm()
        if curses.tigetnum('colors') < 8:
            raise EnvironmentError, 'Not enough colors available.'
        self.curses = curses
        setf = curses.tigetstr('setaf')
        setbg = curses.tigetstr('setab')
        self.colormap = {
            'DEBUG':    curses.tparm(setf, curses.COLOR_BLUE),
            'INFO':     curses.tparm(setf, curses.COLOR_GREEN),
            'WARNING':  curses.tparm(setf, curses.COLOR_YELLOW) +
                curses.tparm(curses.tigetstr('bold'), curses.A_BOLD),
            'ERROR':    curses.tparm(setf, curses.COLOR_RED),
            'CRITICAL': curses.tparm(setf, curses.COLOR_WHITE) +
                curses.tparm(curses.tigetstr('bold'), curses.A_BOLD) +
                curses.tparm(setbg, curses.COLOR_RED),
            'NOTSET':   curses.tigetstr('sgr0')
            }

    def emit(self, record):
        try:
            msg = self.format(record)
            levelname = record.levelname
            out = sys.__stdout__  # in case redirected by filelogger, etc
            if levelname in msg:
                part1, part2 = msg.split('%s ' % levelname, 1)
                out.write(part1)
                ctext = '%s%s%s ' % ( self.colormap.get(levelname, ''),
                    levelname, self.colormap.get('NOTSET') )
                out.write(ctext)
                print >> out, part2
            else:
                print >> out, msg
        except:
            self.handleError(record)


class _PlainTextSocketHandler(logging.handlers.SocketHandler):
    'Overrides the standard SocketHandler to send text instead of pickles.'
    def emit(self, record):
        try:
            msg = self.format(record)
            if not self.sock:
                self.sock = self.makeSocket()
            self.send('%s\n' % msg)
        except:
            self.handleError(record)

# Create a null handler to avoid "no handler" error messages
class _NullHandler(logging.Handler):
    def emit(self, record):
        pass
if _log.handlers:                   # secondary inits, handle module reload
    if _log.handlers[0].__class__.__name__ == _NullHandler.__name__:
        _nullh = _log.handlers[0]   # restore orig _nullh to test in get_logger
    else: _nullh = _NullHandler()
else:
    _nullh = _NullHandler()         # first init, no handlers yet
    _log.addHandler(_nullh)         # install handler to quiet warning msg


# Functions
# ---------------------------------------------------------------------
def _log_report(exception_obj=None):
    'A generic debug logging function.'
    if exception_obj:   func = _log.error
    else:               func = _log.debug
    func('%s: %s' % (sys._getframe(1).f_code.co_name,
        sys._getframe(1).f_locals) )


def check_plan(autostart=True):
    '''
        Ask the Transmission Client to check for a new plan.xml file.

        Options:
            autostart       - Start the Transmission Client service if needed.
    '''
    import pythoncom
    global _netic
    if autostart:
        from scalatools import start_svc
        start_svc(_netic_svc)
    try:
        # don't cache netic, it doesn't work more than once # if not _netic:
        _netic = COMObject(_netic_name)
        _netic.CheckPlanNow()
        _log.info('called.')
    except pythoncom.com_error, err:
        errstr = '%s\n\nPlayer Transmission Client (%s) not available.' % (
            str(err), _netic_name)
        _log.error( errstr.replace('\n', '  ') )
        raise _ObjectNotAvailable, errstr
    except Exception, err:
        _log_report(err)


def get_logger(*details, **destinations):
    '''
        A convenience function that returns a standard python logger object.
        http://docs.python.org/library/logging.html (#logger-objects)

        Keyword Arguments (**destinations):
            level               - Specifies the default logging level, else:
                                  logging.WARN.  Also accepts a string in:
                                  {debug|info|warn|error|critical}
            format              - Specifies the default record format, else:
                                  '%(asctime)s %(levelname)s %(message)s'
            datefmt             - Specifies date format for asctime above,
                                  default: '%Y-%m-%d %H:%M:%S'

            These arguments accept a testable item (e.g. Boolean) as value.
            ---------------------------------------------------------------
            scala               - Scala logging system
            ntevt               - Windows NT Event Log
            con                 - Console stdout w/color (default: True)
            con_nocolor         - Console stdout

            The following require a specific value.  Multiple locations of the
            same type can be configured by appending a char, e.g. "2"
            ---------------------------------------------------------------
            svar = 'var_name'   - Write text to a Scala variable.
            net = 'host[:port]' - To a network host, default port: 8400.
            file = 'c:/log.txt' - Files: Forward or backslashes acceptable.
            smtp = (m,f,t,s,c)  - SMTP Mail, ERROR+ only.  Pass a tuple with
                                  the same args as SMTPHandler, see Py docs.
            http = (h,p,m)      - Pass a tuple with same args as HTTPHandler.
            rotf|trtf = (f,...) - RotatingFileHandler, TimedRotatingFileHandler

        Arguments (*details):
            If a more flexible configuration is needed, a number of dictionaries
            containing destination details can be passed for finer control:
                keys:   One of the following: 'typ', 'arg', 'fmt', 'lvl'
                vals:   One of the corresponding values described above.
        Returns:
            A standard python logger object.
        Note:
            Use of logging.shutdown() is not needed, and may cause problems on
            subsequent runs since Designer/Player keeps the interpreter open
            until exit.  Therefore it is not permitted to modify the logger
            object from this function, although it can be done directly.

        Examples:
            1. The simplest, pass warning and above to the console:
                from scalalib import get_logger
                log = get_logger()
                log.info('Byyye your commaaand.')

            2.  Multiple destinations, with a few of the same type:
                log = get_logger( level='debug', scala=False, con=1,
                    net='localhost:5292', file1='c:/1.txt', file2='c:/2.txt' )
                log.warn("Don't cross the streams!")

            3. Finer control:  Send info+ to a net host, mail critical errors:
                logmail = { 'typ':'smtp', 'arg':(m,f,t,s), 'lvl':'critical' }
                # using a dict constructor is a bit easier to type:
                lognet = dict(typ='net', arg='localhost:5150',
                    fmt='%(message)s', lvl='info')
                log = get_logger(logmail, lognet)
                log.critical('You have %s seconds to reach minimum safe distance.')
    '''
    if _nullh in _log.handlers:
        try:                _log.removeHandler(_nullh)  # prevent race condition
        except ValueError:  pass
        # log is empty. Test is necessary since Designer runs interpreter
        # multiple times without exit.  Duplicate handlers create many problems.
        destinations.setdefault('con', True)
        level = destinations.pop('level', None)
        if level:
            if type(level) is str:
                level = { 'CRITICAL':logging.CRITICAL, 'ERROR':logging.ERROR,
                    'WARN':logging.WARNING, 'WARNING':logging.WARNING,
                    'INFO':logging.INFO, 'DEBUG':logging.DEBUG,
                    }.get(level.upper(), logging.NOTSET)
            _log.setLevel(level)
        else:   level =  logging.NOTSET
        format = destinations.pop('format',
            '%(asctime)s %(levelname)-8s %(funcName)s: %(message)s')
        short_fmt = '%(levelname)-8s %(funcName)s: %(message)s'
        datefmt = destinations.pop('datefmt', '%Y-%m-%d %H:%M:%S')

        # convert simple destinations into detail blobs:
        for k,v in destinations.items():
            detail = dict(typ=k, arg=v, lvl=level, fmt=format, copied=1)
            details += (detail,)

        for dest in details:  # where will we be logging to?
            handler = None
            htype = dest['typ'].lower()  # type must exist or KeyError
            arg = dest['arg']
            myfmt = format;  mylvl = level
            if arg:
                if htype == 'scala':
                    handler = _ScalaLogHandler()
                    myfmt = short_fmt
                elif htype == 'ntevt':
                    handler = logging.handlers.NTEventLogHandler(__name__)
                    myfmt = short_fmt
                elif htype == 'con':
                    try:
                        if not sys.stdout.isatty():
                            raise EnvironmentError, ': not a tty, color disabled.'
                        elif sys.platform.startswith('win'):
                            handler = _Win32ColorConHandler()
                        else:
                            handler = _CursesConHandler()
                    except Exception:
                        handler = logging.StreamHandler(sys.stdout)
                elif htype == 'con_nocolor':
                    handler = logging.StreamHandler(sys.stdout)
                elif htype.startswith('svar'):
                    handler = _ScalaVarHandler(arg)
                    myfmt = short_fmt
                elif htype.startswith('net'):
                    port = _def_logport;  host = arg
                    if ':' in host:  host, port = host.split(':')
                    handler = _PlainTextSocketHandler(host, int(port))
                elif htype.startswith('file'):
                    handler = logging.FileHandler(arg)
                elif htype.startswith('rotf'):
                    handler = logging.handlers.RotatingFileHandler(*arg)
                elif htype.startswith('trtf'):
                    handler = logging.handlers.TimedRotatingFileHandler(*arg)
                elif htype.startswith('http'):
                    handler = logging.handlers.HTTPHandler(*arg)
                elif htype.startswith('smtp'):
                    handler = logging.handlers.SMTPHandler(*arg)
                    if mylvl < logging.ERROR:   # minimize mail by default
                        mylvl = logging.ERROR
                else:
                    raise TypeError('Incorrect destination type: "%s"' % htype)

                # detailed destination settings take precedence if they exist
                if not dest.get('copied'):  # copied use defaults
                    mylvl = dest.get('lvl') or mylvl
                    myfmt = dest.get('fmt') or myfmt
                handler.setLevel(mylvl)
                handler.setFormatter(logging.Formatter(myfmt, datefmt))
                _log.addHandler(handler)

        _log.shutdown = logging.shutdown  # for convenience, not needed Py 2.4+?
        _log.debug( 'logging destinations: %s' % (details,) )
    return _log


def get_metaval(name, filename='ScalaNet:\\metadata.xml'):
    'Deprecated and moved to scalatools.  Please use the new version.'
    import scalatools as st
    return st.get_metaval(name, filename)


def get_scriptdir():
    '''
        Returns the current working folder of the script,
        If there is an error, returns None.
    '''
    global _player
    try:
        if not _player:  _player = COMObject(_player_name)
        return _player.ScriptDir
    except Exception, err:
        _log_report(err)
        return None


def import_mod(name):
    '''
        Search for a module, import, and return if found.

        Argument:
            name            - The name of a module to search for, using
                              scalatools.find_file().
        Returns:
            A python module object.  Raises ImportError if not found.
        Example:
            from scalalib import import_mod
            mymod = import_mod('mymod')  # .py not necessary
    '''
    if not name: raise ValueError, 'name must not be blank.'
    try:
        return sys.modules[name]
    except KeyError:
        import imp
        import scalatools as st
        name = os.path.splitext(name)[0]  # remove any extension

        # search for the file
        try:  modpath = st.find_file('%s.pyc' % name)
        except IOError:
            try: modpath = st.find_file('%s.py' % name)
            except IOError:
                errstr = '"%s" not found.' % name
                _log_report(errstr)
                raise ImportError, errstr

        _log.info('"%s" as "%s"' % (modpath, name) )
        if modpath.lower().endswith('.pyc'):
            try:    # module could be from an old version of python
                return imp.load_compiled(name, modpath)
            except ImportError:  # try again with .py
                return imp.load_source(name, modpath[:-1])
        elif modpath.lower().endswith('.py'):
            return imp.load_source(name, modpath)


def install_content(abspath, subfolder='', autostart=True):
    r'''
        Copies a file to the local Scala Content: folder.

        Argument:
            abspath         - A file (specified by its absolute path) to copy.
        Options:
            subfolder       - Place it into a subfolder to group related files.
            autostart       - Start the Transmission Client service if necessary.
        Notes:
            Installed files may be found later using a Scala-style virtual path
            string, passed to lock_content, e.g.:
                lock_content(r'Content:\filename.ext')
    '''
    import pythoncom
    global _netic
    if not os.path.exists(abspath):
        raise IOError, 'File "%s" does not exist.' % abspath
    if autostart:
        from scalatools import start_svc
        start_svc(_netic_svc)

    try:
        # don't cache netic, it doesn't work more than once # if not _netic:
        _netic = COMObject(_netic_name)
        _netic.IntegrateContentLocally(abspath, subfolder)
        _log.info(abspath)
    except pythoncom.com_error, err:
        errstr = '%s\n\nPlayer Transmission Client (%s) not available.' % (
            str(err), _netic_name)
        _log.error( errstr.replace('\n', '  ') )
        raise _ObjectNotAvailable, errstr
    except Exception, err:
        _log_report(err)


def lock_content(scalapath, report_err=True):
    r'''
        Locks a content file so the player doesn't try to remove it.

        Argument/Option:
            scalapath       -  A Scala-style virtual path, e.g.:
                               "Content:\file.ext"
            report_err      -  Log errors.
        Returns:
            The Windows path to the affected file.
            If the file is not found or there is an error, returns None.
        Example:
            from scalalib import lock_content
            winpath = scalalib.lock_content('Content:\example.png')
    '''
    class _StringAndLock(unicode):
        '''A subclass of a string that carries a Scala lock object around with
        it.  The lock will be unlocked upon deletion when the object falls out of
        scope or is deleted explicitly.'''
        def __del__(self):
            if hasattr(self, 'lockObj'):
                _log.debug('unlock_content: "%s"' % scalapath)
                self.lockObj.UnlockScalaFile()
    try:
        lockObj = COMObject(_filelock_name)
        windows_path = lockObj.LockScalaFile(scalapath)

        # Add the lock into the string, to unlock upon its deletion.
        windows_path = _StringAndLock(windows_path)
        windows_path.lockObj = lockObj

        _log.info( '"%s" @ "%s"' % (scalapath, windows_path) )
        return windows_path
    except Exception, err:
        if report_err: _log_report(err)
        return None


def log_external(message, errcode=1001, module='', autostart=True):
    '''
        Writes a custom message to the Scala log and Content Manager Player
        Health Screen.  Tries Player interface, then InfoNetwork.
        Arguments:
            message         The message to log.
        Options:
            errcode         Error code, see notes below.
            module          The name of the source of the message.
            autostart       If using InfoNetwork, whether to start service.
        Notes:
            https://license.scala.com/readme/ScriptingAutomation.html#toc_CustomProblems
    '''
    import pythoncom
    global _player
    if not _player:  _player = COMObject(_player_name)
    try:
        _player.LogExternalError(errcode, module, message)
    except UnicodeError:
        _player.LogExternalError(errcode, module, message.encode('UTF-8'))
    except pythoncom.com_error, err:   # do not log this; creates a loop.
        print 'COM Error: %s' % err
        global _netic
        if autostart:
            from scalatools import start_svc
            start_svc(_netic_svc)
        # don't cache netic, it doesn't work more than once :/
        _netic = COMObject(_netic_name)
        try:
            _netic.LogExternalError(errcode, module, message)
        except pythoncom.com_error: pass
        except UnicodeError:
            _netic.LogExternalError(errcode, module, message.encode('UTF-8'))


def _log_scala(message):
    'Writes the given message string to the Scala Player Log file, IC.log.'
    import pythoncom
    global _player
    if not _player:  _player = COMObject(_player_name)
    try:
        _player.Log(message)
    except pythoncom.com_error, err:
        print 'COM Error: %s' % err     # do not log this; creates a loop.
    except UnicodeError:
        _player.Log(message.encode('UTF-8'))


def publish(scriptlist, targeturl, targetfolder='', logfilename='',
    editpassword='', options='', autostart=True):
    r'''
        Performs the equivalent of the Publish to Network function of Scala
        Designer5.  Requires the Scala Publish Automation EX Module5 which is an
        additional software component that is installed seperately.

        Arguments:
            scriptlist      - A string containing the absolute paths of one
                                or more script files to publish, one per line,
                                or alternately, a python list of them.
            targeturl       - Publish location path/URL with username and passwd.
                                Examples:
                                - UNC:      \\server\share\folder
                                - FTP URL:  ftp://user:pass@host[:port]/folder/
                                - HTTP/s Content Manager URL:
                                    http://user:pass@host[:port]/folder?netname
            targetfolder    - Sub-folder into which to publish
            logfilename     - Absolute path to a log file to report progress,
                                otherwise to: "%TEMP%\pub_log.txt".
            editpassword    - Optional password to apply to published script(s).
            options         - A string containing zero or more of these flags:
                                - 'd': Show progress GUI.
                                - 'i': Ignore errors.
                                - 'f': Do NOT include fonts.
                                - 'w': Do NOT include wipes.
                                - 'x': Skip cleanup.
                                - 'p': Use passive FTP.
            autostart       - Start the Publisher service if necessary.
        Returns:
            handle          - A unique handle for use with publish_check().

        Example:
            # See the sca_publisher.py script for a general solution.
            import time, glob, scalalib as sl
            targeturl = 'http://user:passwd@mycm.com:8080/ContentManager?MyCo'
            scripts = glob.glob('*.sca')
            pubhandle = sl.publish(scripts, targeturl, options='d')
            while True:
                time.sleep(3)
                status = sl.publish_check(pubhandle)
                statstr = ('Publishing script %(currentscriptnum)s of %(numberofscripts)s'
                    + ' - %(overallpercentdone)3.3s%% complete, %(currentscriptname)s ')
                print statstr % status
                if status.get('overallpercentdone') == 100: break
    '''
    import pythoncom
    global _publshr
    if autostart:
        from scalatools import start_svc
        start_svc(_pub_svc)

    # massage parameters to make sure paths are absolute
    if type(scriptlist) is list:
        scriptlist = [ os.path.abspath(x) for x in scriptlist ]
        scriptlist = '\n'.join(scriptlist)
    elif type(scriptlist) is str:
        scriptlist = os.path.abspath(scriptlist)
    if not logfilename:
        logfilename = os.path.join(os.environ['TEMP'], 'pub_log.txt')
    else:
        logfilename = os.path.abspath(logfilename)
    local_opts = locals()                       # log parameters

    try:
        if not _publshr:
            _publshr = COMObject(_publshr_name)
        pubhandle = None

        _log.debug('options: %s' % local_opts )
        try:
            censoredurl = targeturl  # censor url if needed.
            if ( targeturl.lower().startswith('http')
                or targeturl.lower().startswith('ftp') ):
                censoredurl = targeturl.split('//', 1)
                censoredurl = '%s%s%s%s' % (censoredurl[0], '//', 'xxx:xxx@',
                    censoredurl[1].split('@',1)[1])
            _log.info('publishing to %s' % censoredurl)
        except IndexError:
            _log.info('publishing to %s' % targeturl)

        if targetfolder:
            pubhandle = _publshr.GoPublishFolder(scriptlist, targeturl,
                targetfolder, logfilename, editpassword, options)
        else:
            pubhandle = _publshr.GoPublish(scriptlist, targeturl, logfilename,
                editpassword, options)
        if pubhandle == None:
            _log.warn('Publish operation returned None.  Is the dongle present?')
        return pubhandle

    except pythoncom.com_error, err:
        errstr = ('%s: %s services not available.  Is it installed, running, ' +
            'and not disabled?') % (err.__class__.__name__, _publshr_name)
        _log.critical(errstr)
        raise err
    except Exception, err:
        _log_report(err)
        raise err


def publish_check(pubhandle):
    '''
        Checks the status of a Scala publishing operation.

        Argument:
            pubhandle           - A publishing handle returned from publish().
        Returns:
            A status dictionary with the following keys:

            numberofscripts     - Total number of scripts in this operation.
            currentscriptnum    - Number in sequence of script currently being
                                    published, starting with 1.
            currentscriptname   - Name of script currently being published, no
                                    path or extension.
            scriptpercentdone   - Current script progress 0-100 (%)
            overallpercentdone  - Overall progress 0-100 (%)
            completedscripts    - A string listing successfully publish scripts,
                                    one name per line.
            failedscripts       - A string listing all scripts that failed to
                                    publish, one name per line.
            allerrors           - A string listing all errors encountered in
                                    this publish operation
    '''
    import pythoncom as _pythoncom
    global _publshr
    try:
        if not _publshr:
            _publshr = COMObject(_publshr_name)

        (numberofscripts, currentscriptnum, currentscriptname,
            scriptpercentdone, overallpercentdone, completedscripts,
            failedscripts, allerrors) = _publshr.CheckPublish(pubhandle)
        if overallpercentdone == None:
            _log.warn('Publish returned None.  Is the dongle present?')

        # create a dictionary of all local vars not starting with "_"
        # list comp works in 2.3 unlike gen expression
        status = dict( [ x for x in locals().items()
                         if not x[0].startswith('_') ] )
        _log.debug(status)
        return status

    except _pythoncom.com_error, err:
        _log.error( '%s: %s not available.' % (err, _publshr_name) )
        raise err
    except Exception, err:
        _log_report(err)


def quit_player():
    '''
        Signals the player to shut down gracefully, by sending the ESC keystroke.
        There is a possiblity it may not succeed if the keystroke is lost.
    '''
    import scalatools
    _log.info('called.')
    scalatools.send_key('escape')


def restart_play():
    'Restart Playback on the Scala Player.'
    import pythoncom
    global _runic
    try:
        # don't cache obj, doesn't work more than once # if not _runic:
        _runic = COMObject(_runic_name)
        _log.info('called.')
        _runic.RestartPlayback()
    except pythoncom.com_error, err:
        errstr = '%s\n\nScala Player (%s) not available.' % (
            str(err), _runic_name)
        _log.error( errstr.replace('\n', '  ') )
        raise _ObjectNotAvailable, errstr
    except Exception, err:
        _log_report(err)


time._orig_sleep = time.sleep  # for backward compatibility w/sleep wrapper
def sleep(msecs):
    '''
        Pause execution for the specified interval specified in milliseconds.

        Notes:
            This function can be useful at times to give the player time to
            notice shared variables have changed.
            If ScalaPlayer.Sleep() is available, this function will use it.
            Otherwise, it will fall back on time.sleep().
    '''
    import pythoncom
    global _player, sleep_was_successful
    try:
        if not _player:  _player = COMObject(_player_name)
        _player.Sleep(msecs)
        _log.debug('Scala sleep complete.')
        sleep_was_successful = True
    except pythoncom.com_error, err:
        _log.debug('%s' % err)
        if sleep_was_successful:        # we had the Player once, but lost
            sys.exit(9)                 # at shutdown, don't hang up :/
        else:                           # we never had the Player, cmd-line?
            time.sleep(msecs/1000.0)    # accepts whole float seconds


def thumbnail_gen(scriptpath, filename, width=96, height=96,
    options='', pagename='', xmltext='', autostart=True, **templ_args):
    r'''
        Generates thumbnails of Scala Scripts/Templates.  Requires the Scala
        Server Support Service from Content Manager.

        Arguments:
            scriptpath      - The full path to the Scala Script.
            filename        - Full path to desired image (.jpg, .jpeg, .png)
            width           - Thumbnail width in pixels
            height          - Thumbnail height in pixels
            options         - A string that can contain one of these flags:
                                - 'rl': Rotate 90 degrees left
                                - 'rr': Rotate 90 degrees right
                                - 'ru': Rotate 180 degrees (upside down)
                                - 'k':  Keep aspect
            pagename        - Name of the page to generate, defaults to first.
                                Ignored when scriptpath points to a template.
            xmltext         - An XML snippet that defines template fields, e.g:
                                <ingredients>
                                    <text name="Headline">Breaking News</text>
                                    <boolean name="Enabled">On</boolean>
                                    <integer name="age">123</integer>
                                    <real name="price">1.23</real>
                                    <filename name="Logo">C:\logo.png</filename>
                                </ingredients>
            templ_args      - Alternately, additional keyword args passed will
                                create xmltext automatically; type is inferred.
                                eg. (Enabled=True, Logo=r'c:\logo.png')
            autostart       - Start the Server Support service if necessary.
        Returns:
            numthumbs       - The number of thumbnails created, as there may be
                                more than one page in a script.
        Example:
            from scalalib import thumbnail_gen
            thumbnail_gen('d:\\tmpl.sca', 'd:\\thbn.jpg', 96, 96, options='k',
                tmpl_CityName='Kathmandu', tmpl_Greeting='d:\\Namaste.jpg')
    '''
    import pythoncom
    global _thumbnl
    if autostart:
        from scalatools import start_svc
        start_svc(_thumb_svc)
    try:
        if not _thumbnl:   # initialize vars
            _thumbnl = COMObject(_thumbnl_name)
        errmsgs = None
        numthumbs = 1

        if templ_args:
            xmltext = '<ingredients>\n'
            for name,value in templ_args.items():
                if   type(value) is bool:
                                            vartype = 'boolean'
                                            if value:   value = 'On'
                                            else:       value = 'Off'
                elif type(value) is int:    vartype = 'integer'
                elif type(value) is float:  vartype = 'real'
                elif type(value) is str or type(value) is unicode:
                    if (len(value) > 3 and value[1] == ':' and
                        '\\' in value):     vartype = 'filename'
                    else:                   vartype = 'text'
                else: raise 'error: gen_thumbs - unknown type passed.'
                xmltext += '    <%s name="%s">%s</%s>\n' % (
                    vartype, name, value, vartype)
            xmltext += '</ingredients>\n'
            _log.debug('xmltext generated: %r' % xmltext )

        if xmltext:
            _thumbnl.GeneratePreviewThumbnails(scriptpath, xmltext,
                filename, width, height, options, numthumbs, errmsgs)
        else:
            _thumbnl.GenerateThumbnail(scriptpath, pagename,
                filename, width, height, options, errmsgs)

        _log.info('Generated %s thumbnail(s) of "%s".' % (numthumbs, scriptpath))
        if errmsgs:  _log.warn(errmsgs)
        return numthumbs

    except pythoncom.com_error, err:
        _log.error( '%s: %s' % (err, _thumbnl_name) )
        raise err
    except Exception, err:
        _log_report(err)

