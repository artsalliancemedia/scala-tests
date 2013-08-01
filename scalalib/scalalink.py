r'''
    scalalink.py - (C) 2009-2012 Scala, Mike Miller
    This module houses a simple command-based communications framework.
    Send questions regarding this module to mike dot miller at scala dot com.

    Place in the lib/site-packages folder of your Scala for Python installation.

    Command line usage:
        scalalink.py [options] [text] [to send]
    Scala Script usage:
        Share the parameters listed below as Scala variables, prepended with
        "lnk_", e.g.:  lnk_port, lnk_message.

    Introduction:
        Link objects:  A communication link consists of a sender and a listener,
        the sender dispatching short messages to a listener in order to control
        it.  These messages can be useful to trigger Scala or external hardware
        events, and may be sent over several possible transports.  For example,
        over a Serial cable, or Multicast UDP to multiple hosts across a LAN.

        Commands:  Each message may contain a Scala text command, encoded in
        UTF-8, and has the following structure on the wire.  Items in angle
        brackets are required, square optional.  Brackets are _not_ included:
            '<HEADER> <commandname> [arg1] "[arg2 w/spaces]" [...] <\n>'

        Responses (not available with UDP transports) are of the following form:
            '<HEADER> <OK|ERROR> [Optional descriptive text] <\n>'

    Notes:
        - As shown above, the command text supports POSIX-style quoting/escaping
            of arguments, see the following document for parsing rules:
            http://docs.python.org/library/shlex.html
        - Experimental unicode support is present; a patched shlex is included.
        - The preceeding header and trailing newline are added and removed
            automatically by these methods, there is no need to process them.
        - Built-in commands are listed in the function listing below.  These
            commands may be overridden and additional ones created.

    Sending messages with Link.send():
        Argument:
            message         - The bare text command to send.
        Link options when sending:
            timeout <float> - Number of seconds to wait before giving up on a
                              connection attempt.  None equals no timeout.
            delay <float>   - A delay in secs during the connection to give the
                              host a chance to respond.  This is necessary
                              on some hardware listeners.
            tries           - Try this many times before giving up.
            wrap            - Add header to front and newline to end of message.
                              Set to False to send the bare message only.
            waitstr         - Wait for this response before sending.
        Network-specific Link options:
            host            - The network host to send to, defaulting to
                              'localhost', for multicast-udp: '225.100.100.100'.
            port            - Port number, the default is 7700.
            ttl             - Adjust multicast TTL setting (use caution).
            autoclose       - Close TCP connections after every message.
                              May avoid lockups on exit.  Off by default.
        Serial-specific Link options:
            port            - Port number, the default is 0 or COM1.
            raw             - Send as raw bytes.  Implies wrap=False.
            serialargs      - Additional keyword arguments for serial.Serial():
                              see: http://pyserial.wiki.sourceforge.net/pySerial
        Returns:
            A response, if received, or True on success, False on error.
        Examples:
            1. using Multicast UDP, set a variable on many players:
                from scalalink import MulticastUDPLink, TCPLink, SerialLink
                MulticastUDPLink(ttl=3).send('set foo=bar')
            2. using TCP/IP, play media items:
                link = TCPLink(host='22.1.14.8', port=5150)
                link.send('play "Best of Both Worlds.sca" ')
                link.send('play Good\ Enough.sca')
            3. Serial hello at 19200 baud:
                SerialLink(serialargs=dict(baudrate=19200)).send('ok')
            4. Send a "bare" command across the network:
                from scalalink import UDPLink
                UDPLink(host='hwlighting', wrap=False).send('arbitrary text\n')

    Listening for commands:
        Link.listen() option:
            addhandlers     - A single or sequence of additional callback
                              functions to handle custom commands.  They should
                              be defined as scmd_commandname(*args).
        Link options when listening:
            delay <float>   - Wait this long (in secs) before executing command.
            wrap            - Expect message to contain a header/newline.
            uniparse        - Unicode parser support, default True,
                              Use False to disable if there are parsing issues.
        Network-specific Link options:
            host            - If blank, listen on the first public ip address,
                              default: 'localhost'.
            port            - Port number, the default is 7700.
            timeout <float> - Number of seconds to wait per loop for a connection
                              attempt.  This number also affects how quickly
                              a net listener can be killed, e.g. once every 2s.
                              If a positive float, seconds until timeout.
                              If None, disable timeout (not recommended).
            autoclose       - Close TCP connections after every message.
                              May avoid lockups on exit.  Off by default.
        Serial-specific Link options:
            port            - Port number, the default is 0 or COM1.
            timeout <float> - Number of seconds to wait before giving up on a read.
                              If 0, return immediately after read.
                              If a positive float, seconds until timeout.
                              If None is passed, disable timeout.
            serialargs      - Additional arguments to pass to serial.Serial:
                                http://pyserial.wiki.sourceforge.net/pySerial
        Notes:
            This function will block, waiting for messages.  When using from a
                Scala Script, turn off the Wait option.
            For network listeners, local firewalls must be configured to
                allow python scripts to open and listen on the specified port.
            Listening machines must be on a secure network, behind a NAT,
                and/or using a VPN, etc.  Do *not* create commands that evaluate
                code or execute system commands.  You've been warned.  ;)
        Examples:
            1. Listen for Multicast commands on port 12345, delay a speedy
               machine by .2 seconds:
                from scalalink import MulticastUDPLink, SerialLink
                MulticastUDPLink(port=12345, delay=.2).listen()
            2. Listen for a custom command "foo" on the second serial port:
                def scmd_foo(*args):
                    # do something interesting ...
                    return 'OK BAR ' + str(args)
                SerialLink(port=1).listen(addhandlers=scmd_foo)
'''
if True: # fold init
    import sys, os, time, logging, string
    import scalalib as sl

    __version__ = '1.15'
    _scmd_header = 'SCMD '
    _def_net_port = 7700
    _def_timeout = None
    _def_delay = 0
    _def_tries = 5
    _def_waitstr = ''
    _def_wrap = True
    _def_autoclose = False
    _def_link_responds = True
    _def_transport = 'tcp'
    _def_uniparse = True
    _def_enc = 'utf-8'
    _def_mchost = '225.100.100.100'
    _sleep = sl.sleep    # default sleep
    _timer = None
    _shared_namespace = None
    loggername = 'scalalib.link'
    _log = logging.getLogger(loggername)
    _log.addHandler(sl._nullh)  # quiet "no handler" error messages


# Classes
# ---------------------------------------------------------------------
class _ModeSwitchError(Exception):
    message = 'Transport unable to switch send/recv mode.'
class _SCMDError(Exception): pass


class ScalaComLink(object):
    'Abstract base class representing a communication link, do not instantiate.'
    def __init__(self, header=_scmd_header, timeout=_def_timeout,
        delay=_def_delay, tries=_def_tries, waitstr=_def_waitstr,wrap=_def_wrap,
        autoclose=_def_autoclose, link_responds=_def_link_responds,
        uniparse=_def_uniparse, **kwargs):
        self.header = header
        self.timeout = timeout
        self.delay = delay
        self.tries = tries
        self.waitstr = waitstr
        self.wrap = wrap
        self.autoclose = autoclose
        self.link_responds = link_responds
        self.uniparse = uniparse
        for key in kwargs.keys():
            setattr(self, key, kwargs[key])

        self.conn = None
        self.listening = False
        self.mode = 'default_send'
        self.log = _log                 # keep so log is around at obj del time.
        self.scmd_handlers = dict([     # collect local scala commands
            ( x.replace('scmd_','',1), globals()[x] ) # (name, value)
            for x in globals().keys()   # find _scmd_ functions in module
            if x.startswith('scmd_')
            ])

    def _close(self):
        try:
            if self.conn: self.conn.close()
        except Exception, e:
            self.log.warning('unable to close object. %s: %s' %
                (e.__class__.__name__, e) )
        self.conn = None

    def _connect(self):
        raise NotImplementedError, 'subclasses must implement.'

    def _connect_listener(self):
        raise NotImplementedError, 'subclasses must implement.'

    def _handle_response(self):
        success = False
        try:
            if self.delay: time.sleep(self.delay/2.0)    # then recv
            response = self._readline()
            if response is None:  raise TypeError, 'No response.'
            response = response.decode('utf-8')
            if self.autoclose: self._close()
            _log.debug('recv <<<: %r' % response)
            if self.wrap and response:                    # unwrap
                response = response.replace(self.header, '').rstrip()

            respcode = response.replace(self.header, '').split()
            if respcode and respcode[0] == 'ERROR':
                raise _SCMDError, ' '.join(respcode[1:])
            success = response or True
        except Exception, e:
            _log.error('%s: %s' % (e.__class__.__name__, e) )
        return success

    def listen(self, addhandlers):
        '''
            Listen for Scala text commands and handle them.
            Option:
                addhandlers     - A single or sequence of additional callback
                                  functions to handle custom commands.  They
                                  should be named scmd_commandname(*args).
        '''
        if self.mode == 'send':
            _log.error(_ModeSwitchError.message)
            raise _ModeSwitchError, _ModeSwitchError.message
        self.mode = 'listen'
        global _shared_namespace
        _shared_namespace = None    # reset each session
        if addhandlers is None:
            addhandlers = ()
        elif type(addhandlers) not in (list, tuple):
            addhandlers = (addhandlers,)
        for handler in addhandlers:  # added functions override standard
            name = handler.__name__.replace('scmd_', '', 1)
            self.scmd_handlers[name] = handler
            _log.info('registered cmd "%s" with handler %s.'  % (name, handler))
        self.listening = True
        if self.uniparse:
            try:
                import uni_shlex as shlex  # patched for unicode
            except ImportError:
                import shlex
                self.uniparse = False
        else:
            import shlex
        self.parser = shlex

    def _process_cmd(self, cmdline):
        '''
            Handle Scala text commands.
            Arguments:
                cmdline         - e.g.: 'SCMD <command> [arg1] "[arg2 ...]"'
        '''
        try:
            if not self.uniparse:
                cmdline = cmdline.encode('latin-1', 'backslashreplace') # cheesy
            cmdlist = self.parser.split(cmdline)
            _log.info('received: %s' % cmdlist)
            if self.wrap:  # check
                if len(cmdlist) > 1 and cmdlist[0] == self.header.strip(): pass
                else: raise TypeError, 'unrecognized data received.'
                command = cmdlist[1].lower()
                args = cmdlist[2:]
            else:
                command = cmdlist[0].lower()
                args = cmdlist[1:]

            if command in self.scmd_handlers:
                func = self.scmd_handlers[command]
                result = func(*args) or 'OK'  # if None, return 'OK'
                return '%s%s\n' % ((self.header if self.wrap else ''),  result)
            else:
                raise ValueError, 'unrecognized command passed.'

        except Exception, e:
            import traceback
            errstr = '%s:\n  %s' % (type(e), traceback.format_exc())
            _log.error(errstr)
            return '%sERROR %s\n' % (self.header, errstr.split('\n')[-2])

    def _readline(self):
        return self.conn.readline()

    def _render_msg(self, message):
        if '\\' in message:         # render escape seqs
            message = message.replace('\\r', '\r')
            message = message.replace('\\n', '\n')
            message = message.replace('\\t', '\t')
        if self.wrap:
            message = self.header + message
            if not message.endswith('\n'): message += '\n'
        return message

    def send(self, message, encoding=_def_enc):
        '''
            Sends a text message, useful to trigger Scala or hardware events.
            Argument:
                message         - The bare text command to send.
                encoding        - The char encoding of message, if not UTF-8
                                  or unicode object.
        '''
        if len(message) == 0: return None
        if self.mode == 'listen':
            _log.error(_ModeSwitchError.message)
            raise _ModeSwitchError, _ModeSwitchError.message
        if hasattr(self, 'raw') and self.raw:
            pass
        elif isinstance(message, basestring) and not isinstance(message, unicode):
            message = unicode(message, encoding=encoding)
        message = self._render_msg(message)
        linenum = 'unknown'
        success = False

        for i in range(self.tries):
            try:
                if not self.conn: self._connect()
                if self.delay: time.sleep(self.delay/2.0)  # hold on for a sec
                if hasattr(self, 'raw') and self.raw:
                    self._write(message)
                else:
                    self._write(message.encode(_def_enc))
                if self.delay: time.sleep(self.delay/2.0)
                if hasattr(self.conn, 'flush'): self.conn.flush()
                _log.info('sent >>>: %r' % message)
                success = True;  break  # exit the for loop on success
            except Exception, e:
                linenum = sys.exc_info()[2].tb_lineno
                self.conn = None

        if success and self.link_responds:
            success = self._handle_response()  # command status may be False
        if not success and locals().get('e'):  # show the error once
            _log.error('%s: %s, line: %s' % (e.__class__.__name__, e, linenum) )
        return success

    def _waitstr(self):
        while self.waitstr:      # wait for a prompt before continuing
            resp = self._readline()
            match = self.waitstr in resp
            _log.debug('Received: %r, Match: %s' % (resp, match))
            if match: break

    def _write(self, message):
        self.conn.send(message)
        if hasattr(self.conn, 'flush'):  self.conn.flush()

    def __del__(self):
        'Automatic close() on deletion of last reference.'
        try:        self.log.debug('close and delete of the Link object.')
        except:     pass
        finally:    self._close()


class SerialLink(ScalaComLink):
    'Create and handle a communication link over serial cable.'
    def __init__(self, port=0, timeout=3, serialargs={}, raw=False, **kwargs):
        super(SerialLink, self).__init__(**kwargs)
        if type(port) in (str, unicode): port = int(port)
        self.port = port
        self.timeout = timeout
        self.raw = raw
        if self.raw:
            self.wrap = False
            self.link_responds = False
        self.serialargs = serialargs
        import serial
        self.mod = serial

    def _connect(self):
        self.conn = self.mod.Serial(self.port, timeout=self.timeout,
            **self.serialargs)
        self.conn.send = self.conn.write              # standardize interface
        self.conn.recv = self.conn.read
        _log.debug('serial options: %r' % self.conn)
    _connect_listener = _connect

    def listen(self, addhandlers=None):
        '''
            Listen for Scala text commands and handle them.
            Option:
                addhandlers     - A single or sequence of additional callback
                                  functions to handle custom commands.  They
                                  should be named scmd_commandname(*args).
        '''
        super(SerialLink, self).listen(addhandlers)
        try:
            if not self.conn: self._connect()
        except self.mod.serialutil.SerialException, e:
            _log.critical('%s: %s' % (e.__class__.__name__, e) )
            return

        _log.debug('waiting...')
        while self.listening:
            try:
                sys.stdout.write('.')
                line = self._readline().decode('utf-8')
                if line and not line.isspace():
                    print; _log.debug('recv <<<: %r from %s' %
                        (line, self.conn.portstr) )
                    if self.delay: time.sleep(self.delay)  # hold yer horses
                    result = self._process_cmd(line).encode('utf-8')
                    if self.link_responds:
                        self._write(result)
                        if hasattr(self.conn, 'flush'): self.conn.flush()
                        _log.debug('sent >>>: %r' % result)
            except KeyboardInterrupt:
                print; _log.warn('Killed by Ctrl-C.')
                self.listening = False
            except Exception, e:
                print; _log.error('%s: %s' % (e.__class__.__name__, e) )
                self.listening = False
        # end while
        _log.info('exiting.')
        self._close(); return

    def _readline(self):
        line = self.conn.readline()
        if line and ( (line[0] == '\xff') or (line[0] == '\xfe') ):
            _log.warning('spurious char \\xff in read response.')
            line = line[1:]
        return line


class NetworkLink(ScalaComLink):
    'Abstract base class representing a network link, do not instantiate.'
    def __init__(self, host='localhost', port=_def_net_port, timeout=3,
        autoclose=False, **kwargs):
        super(NetworkLink, self).__init__(**kwargs)
        self.host = host
        if type(port) in (str, unicode): port = int(port)
        self.port = port
        self.timeout = timeout
        self.autoclose = autoclose

        import socket
        self.mod = socket
        self.casttype = 'uni'
        self.srvsock = None
        self.waitconn = False
        self._buffer = ''
        self.readsize = 1024

    def _readline(self):
        while True:
            if '\n' in self._buffer:  # return anything in the buffer first
                line, self._buffer = self._buffer.split('\n', 1)
                return line + '\n'
            line = self.conn.recv(self.readsize)
            if line:    self._buffer += line  # timeout, close
            else:       return ''

    def _connect(self):
        self.conn.settimeout(self.timeout)
        _log.debug( '%scast %s: ("%s", %s)' %
            (self.casttype, self.__class__.__name__, self.host , self.port) )

    def _connect_listener(self):
        if self.srvsock:  self.srvsock.settimeout(self.timeout)
        hoststr = self.mod.gethostname()
        if '-' in hoststr:             # check host name
            _log.warn('The character "-" in the hostname may prevent ' +
                'this tool from working correctly: %s' % hoststr)
        if not self.host:
            _log.debug('found: %s' % self.mod.gethostbyaddr(hoststr)[-1])
        _log.debug('%s: ("%s", %s)' %
            (self.__class__.__name__, self.host , self.port) )

    def listen(self, addhandlers=None):
        '''
            Listen for Scala text commands and handle them.
            Option:
                addhandlers     - A single or sequence of additional callback
                                  functions to handle custom commands.  They
                                  should be named scmd_commandname(*args).
        '''
        super(NetworkLink, self).listen(addhandlers)
        import select
        self.modselect = select
        tries = self.tries  # make a copy to modify

        while tries and self.listening:
            try:
                self.clientaddr = None
                if not self.conn: self._connect_listener()

                # Listen for connection in loop
                # -----------------------------------------------------------
                _log.debug('waiting...')
                if self.waitconn: self._wait_conn()

                # check for data then read, but don't block.
                while self.listening:
                    sys.stdout.write('.')
                    inputready, outputready, exceptready = (
                        self.modselect.select(
                            [self.conn], [], [], self.timeout) )
                    if inputready:
                        print;  _log.debug('reading...')
                        try:
                            line = self._readline().decode('utf-8')
                            if line:
                                _log.debug('recv <<<: %r from %s' %
                                    (line, self.clientaddr) )
                                if self.delay: time.sleep(self.delay)  # hold on
                                result = self._process_cmd(line).encode('utf-8')
                                if self.link_responds:
                                    self._write(result)
                                    if hasattr(self.conn, 'flush'): self.conn.flush()
                                    _log.debug('sent >>>: %r' % result)
                            else:  # empty string means socket was closed by conn
                                _log.debug('closing.')
                                self._close();  break
                        except self.mod.error, err:
                            if err.errno == 10035:
                                self.conn.send('%sERROR %s (missing \\n?)\n' %
                                    (self.header, err) )
                                _log.warn('%s (missing \\n?)' % err)
                                self._buffer = ''  # discard bad data
                            else:
                                _log.warn('%s' % err)

                        # process one command and quit--makes IC5 happier.
                        if self.autoclose:
                            self._close();  break
                    _sleep(50)  # tiny sleep so Player can quit

            except self.mod.error, e:
                _log.warn('%s: Already running? Asking existing server to exit.' %e)
                try:
                    self._connect()
                    exitcmd = '%s exit (sent from new server.)\n' % self.header
                    self._write(exitcmd)
                    _log.info('sent >>>: %r' % exitcmd)
                    self._close()
                    self.srvsock = None
                except Exception, e:
                    _log.error('Error: exit cmd to port did not succeed. %s' % e)
                    return
                time.sleep(abs(self.timeout or 0)+1)  # watch for None's and neg
                tries = tries - 1
                continue
            except KeyboardInterrupt:
                self.listening = False
                print; _log.warn('Killed by Ctrl-C.')
            # catching Exception = infinite loop w/ sleep on Scala shutdown :(

        # end while
        _log.info('exiting.')
        self._close()


class TCPLink(NetworkLink):
    '''
        Create and handle network stream connections.
        Notes:
            This Link has higher reliability but more overhead than UDP.
            May suffer delays from TCP Slow Start, to mitigate try to
            keep packets small.
            The parameter "autoclose" is no longer enabled by default.  If
            lockups are encountered on Scala or script exit, reenable.
    '''
    def __init__(self, **kwargs):
        super(TCPLink, self).__init__(**kwargs)
        self.waitconn = True

    def _connect(self):
        self.conn = self.mod.socket(self.mod.AF_INET, self.mod.SOCK_STREAM)
        super(TCPLink, self)._connect()
        self.conn.connect((self.host, self.port))

    def _connect_listener(self):
        self.srvsock = self.mod.socket(self.mod.AF_INET, self.mod.SOCK_STREAM)
        self.srvsock.bind((self.host, self.port))
        self.srvsock.listen(3)
        super(TCPLink, self)._connect_listener()

    def _wait_conn(self):
        while self.listening:                 # if tcp, wait for a connection
            try:
                self.conn, self.clientaddr = self.srvsock.accept()  # will time out
                self.srvsock.close(); self.srvsock = None
                break
            except self.mod.timeout:
                sys.stdout.write('.')
                _sleep(50)  # tiny sleep so Player can quit


class UDPLink(NetworkLink):
    '''
        Create and handle unicast network datagram messages.
        May lose a packet occasionally on networks of low connection quality.
    '''
    def __init__(self, **kwargs):
        super(UDPLink, self).__init__(**kwargs)
        self.link_responds = False

    def _connect(self):
        self.conn = self.mod.socket(self.mod.AF_INET, self.mod.SOCK_DGRAM)
        super(UDPLink, self)._connect()
        self.conn.setsockopt(self.mod.SOL_SOCKET, self.mod.SO_REUSEADDR, 1)

    def _connect_listener(self):
        self.conn = self.mod.socket(self.mod.AF_INET, self.mod.SOCK_DGRAM)
        self.conn.bind((self.host, self.port))
        super(UDPLink, self)._connect_listener()

    def _write(self, message):
        self.conn.sendto(message, (self.host, self.port))


class MulticastUDPLink(UDPLink):
    '''
        Create and handle network datagram messages broadcast to the network.
        May lose a packet occasionally on networks of low connection quality.
    '''
    def __init__(self, host=_def_mchost, ttl=2, **kwargs):
        super(MulticastUDPLink, self).__init__(**kwargs)
        self.host = host
        self.ttl = ttl
        self.casttype = 'multi'

    def _connect(self):
        UDPLink._connect(self)
        self.conn.setsockopt(self.mod.IPPROTO_IP, self.mod.IP_MULTICAST_TTL,
            self.ttl)

    def _connect_listener(self):
        import struct
        smod = self.mod
        self.conn = smod.socket(smod.AF_INET, smod.SOCK_DGRAM)
        self.conn.setsockopt(smod.SOL_SOCKET, smod.SO_REUSEADDR, 1)
        mreq = struct.pack('4sl', smod.inet_aton(self.host),
            smod.INADDR_ANY)
        self.conn.bind(('', self.port))
        self.conn.setsockopt(smod.IPPROTO_IP, smod.IP_ADD_MEMBERSHIP, mreq)
        super(UDPLink, self)._connect_listener()  # Skip UDP


# Functions
# ---------------------------------------------------------------------
def _get_shared_namespace():
    'Find, cache, and return frame globals holding Scala vars.'
    global _shared_namespace
    if not _shared_namespace:
        for i in range(1, 20):     # Try to find the correct frame
            try:
                if sys._getframe(i).f_globals['__name__'] == '__ax_main__':
                    _shared_namespace = sys._getframe(i).f_globals
                    break
            except KeyError: continue   # not in this frame
            except ValueError: break    # too far
    return _shared_namespace


# define standard Scala text commands
def scmd_ok(*args):
    'Simple keep-alive/ping statement, returns "OK".'
    return 'OK'


def scmd_countdown(interval, command, *args):
    '''
        Start counting down to the given command.  May be used when multicasting
        synchronization messages, in order to mitigate dropped packets.  When
        multiple messages are sent with a decreasing interval, the chances of at
        least one message arriving are greatly increased.

        Arguments:
            interval        - The number of floating-point seconds to wait
                              before execution.
            *args           - The command and any arguments to execute.
        Example:
            countdown 4.5 set x=1
                (wait one second)
            countdown 3.5 set x=1
    '''
    from threading import Timer
    global _timer
    parent = sys._getframe(1).f_locals['self']          # get object

    # cannot access data structures from secondary thread, must send a private
    # message through the network instead.
    if parent.__class__ == MulticastUDPLink:  # do not broadcast again
        sender = UDPLink(port=parent.port, host='localhost')
    else:
        sender = parent.__class__(port=parent.port, host=parent.host)
    cmdline = command + ' ' + ' '.join([ ('"%s"'%x) for x in args ])
    def countdown_wrapper(sender, cmdline):
        'Keeps a reference on needed objects so they aren\'t lost'
        global _timer
        _log.info('sending: ' + cmdline)
        sender.send(cmdline)
        _timer = None
        sender = None

    if _timer:
        _timer.cancel()
        _log.warn('timer reset.')
    _timer = Timer(float(interval), countdown_wrapper, [sender, cmdline])
    _timer.start()

    return 'OK Waiting %s seconds to begin.' % interval


def scmd_exit(*args):
    'Shut down this listener.'
    # search for our object
    sys._getframe(1).f_locals['self'].listening = False


def scmd_goto(pagename):
    '''
        Go to a page in a Scala Script, named <pagename>.

        Note:
            Share a Scala variable named: gotopage
        Example:
            goto displaypage
    '''
    return scmd_set('gotopage=%s' % pagename)


def scmd_log(level, message):
    '''
        Log a message.
        Arguments:
            level           - One of debug, info, warn, error, or critical.
            message         - A string to log, quoted if it contains whitespace.
        Example:
            log info "Brain is fish food."
    '''
    level = logging._levelNames.get(level.upper(), logging.NOTSET)
    _log.log(level, message)


def scmd_increment(varname, step=1):
    '''
        Increment a shared integer variable named <varname> by <step>.
        Example:
            increment num_questions
    '''
    ns = _get_shared_namespace()
    try:
        ns[varname].Value = ( ns[varname].Value + int(step) )
    except KeyError:
        raise NameError, 'variable %s not found.'% varname
    except TypeError:  # ns is None, not subscriptable
        raise NameError, 'Scala namespace not found.'


def scmd_play(filename, triggervar_str='controlstring',
    triggervar_int='controltrigger_i', triggerfname=None):
    r'''
        Trigger media playback.
        Arguments:
            filename        - The name of the media file to play.
            triggervar_str  - A string channel variable to assign the filename.
            triggervar_int  - An integer channel variable to increment.
            triggerfname    - An optional disk filename to write the media
                              filename to, and saved under Player %TEMP% folder.
        Note:
            This version restricts triggerfname to the temp folder for security
            reasons.
        Example:
            play filename.png controlstring controltrigger_i trigger.txt
    '''
    # set parameter string
    scmd_set('%s=%s' % (triggervar_str, filename))
    if triggerfname:  # will pass any IOError to response
        import tempfile
        tmpdir = tempfile.gettempdir()
        triggerfname = os.path.join(tmpdir, os.path.basename(triggerfname))
        _log.debug('writing to: ' + triggerfname)
        f = file(triggerfname, 'w'); f.write('%s\n' % filename); f.close()
    scmd_increment(triggervar_int)


def scmd_restartplay(*args):
    '''
        Restart playback on Player.
        Example:
            restart_play
    '''
    sl.restart_play()


def scmd_send_key(*args):
    '''
        Send a virtual key press event to this listener\'s machine.
        Example:
            send_key f5
    '''
    import scalatools as st
    if not args:  raise TypeError, 'no arguments given.'
    for key in args:
        if not st.send_key(key):
            return 'ERROR key not found.'


def scmd_set(*args):
    '''
        Sets a variable in a Scala Script.
        Arguments:
            name=value      - name/value pair to assign, must be shared or
                              will return error.
        Examples:
            set var1=val1
            set var2=val2 var3="value with spaces"
    '''
    if args:
        ns = _get_shared_namespace()
        notfound = []
        for arg in args:
            varname, value = arg.split('=', 1)
            try:
                ns[varname].Value = value
            except KeyError:
                notfound.append(varname)
            except TypeError:  # ns is None, not subscriptable
                raise NameError, 'Scala namespace not found.'
        if notfound:
            raise NameError, 'variable(s) not found: ' + ', '.join(notfound)
    else:
        raise TypeError, 'no arguments given.'


# When used from command line or Scala Script, specify transport by short name.
_transports = dict([ (k.replace('Link', '').lower(), globals()[k]) # name, class
                for k in globals().keys()
                if k.endswith('Link') ]);  del k


if __name__ == '__main__':                      # Run from command line

    from optparse import OptionParser
    _sleep = lambda msecs: time.sleep(msecs/1000.0)  # convert to whole secs
    _usage = 'Usage: %prog [options] [send] [text]'
    parser = OptionParser(usage=_usage, version=__version__)
    parser.add_option('--additional-help',
        action='store_true', help='Show more extensive help text.')
    parser.add_option('-e', '--char-encoding', metavar='ENC', default=_def_enc,
        help='Specifiy the input character encoding of this terminal.')
    parser.add_option('-d', '--delay', type='int',
        metavar='#', default=_def_delay, help='Hold x sec(s).')
    parser.add_option('-H', '--host', help='The hostname of this link.')
    parser.add_option('-l', '--listen', default=False,
        action='store_true', help='Listen and serve requests on this link.')
    parser.add_option('-p', '--port', type='int', metavar='#',
        help='Port to send to.  Default net:7700, serial:0.')
    parser.add_option('-r', '--tries', type='int', metavar='#',
        help='Number of times to retry if unsuccessful.')
    parser.add_option('-R', '--raw', action='store',
        help='Send raw bytes with SerialLink. (True/False, 0/1)')
    parser.add_option('-t', '--transport', default=_def_transport, metavar='T',
        help='How to connect, i.e: "serial", "tcp", "udp", "multicast-udp".')
    parser.add_option('-T', '--timeout', type='int', metavar='SECS',
        help='How long to wait before giving up.')
    parser.add_option('-v', '--verbose', action='store_true',
        help='Enable verbose output.')
    parser.add_option('-V', '--very-verbose', action='store_true',
        help='Enable debugging output.')
    parser.add_option('-w', '--waitstr', metavar='STR',
        help='Wait for this greeting str before responding.')
    parser.add_option('-W', '--wrap', action='store',
        help='Add header and trailing newline to message. (True/False, 0/1)')
    (opts, args) = parser.parse_args()

    # validate arguments
    if opts.additional_help:
        print __doc__;  parser.print_help()
        sys.exit()
    loglevel = 'warn'
    if opts.verbose:  loglevel = 'info'
    if opts.very_verbose:  loglevel = 'debug'
    log2 = sl.get_logger(level=loglevel)
    listen = opts.listen
    msg = string.join(args)
    if (not msg) and (not opts.listen):         # args are required on send
        parser.print_help()
        sys.exit(3)
    choices = {'true':1, 'on':1, '1':1, 'false':0, 'off':0, '0':0}
    if opts.wrap:   opts.wrap = choices.get(str(opts.wrap).lower(), False)
    if opts.raw:    opts.raw = choices.get(str(opts.raw).lower(), False)
    try:
        transport = _transports[opts.transport.lower().replace('-','')]
    except KeyError:
        log2.error('Unknown transport: %s' % opts.transport)
        parser.print_help()
        sys.exit(4)

    # remove null/unneeded options so they don't overwrite values in Link obj
    del opts.verbose, opts.transport, opts.listen
    for x in [ x for x in opts.__dict__.keys() if getattr(opts,x) is None ]:
        delattr(opts, x)
    options = opts.__dict__
    log2.debug('options: %s | args: %s' % (options, args) )

    # proceed
    if listen:
        transport(**options).listen()
    else:
        result = transport(**options).send(msg, encoding=opts.char_encoding)
        sys.exit(not result) # report if error


elif __name__ == '__ax_main__':                 # Run from scala

    import scala5
    svars = sl.sharedvars(defaults=dict(lnk_listen=False, lnk_transport='tcp'))
    _sleep = scala5.ScalaPlayer.Sleep
    # validate arguments
    if (not svars.lnk_message) and (not svars.lnk_listen):  # required on send
        raise TypeError, 'message is not defined.'
    try:
        transport = _transports[svars.lnk_transport.lower().replace('-','')]
    except KeyError:
        _log.error('Unknown transport: %s' % svars.lnk_transport)
        raise

    options = dict([ (str(k).replace('lnk_', ''), v)        # build options dict
                            for k,v in svars.__dict__['main'].items()
                            if k.startswith('lnk_')  ])

    message = svars.lnk_message
    if 'message' in options:    del options['message']      # remove unnec vars
    if 'transport' in options:  del options['transport']
    if 'listen' in options:     del options['listen']

    if svars.lnk_listen:
        transport(**options).listen()
    else:
        transport(**options).send(message)

else:                                           # imported as module
    try:
        import scala5
        _sleep = scala5.ScalaPlayer.Sleep       # if available and functional
        _sleep(1)
    except:
        _sleep = lambda msecs: time.sleep(msecs/1000.0)  # convert to whole secs
