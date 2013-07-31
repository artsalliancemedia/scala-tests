'''
    scalaprov.py - (C) 2009-2012 Scala, Mike Miller
    A toolbox to automate the provisioning of Scala Players.
    Send questions regarding this module to mike dot miller at scala dot com.

    Place in the lib/site-packages folder of your Scala for Python installation.

    Command line usage:
        %prog [options] [-h for help]

    Examples:
        # Create a new player via webservices, assign it:
        scalaprov.py -a usr:pwd -b http://myco.com:8080/ContentManager/ -n MyCo
            --build-netic --create "%COMPUTERNAME%" --channel Demo --auto-display

        # Assign an existing player w/o webservices and restart
        scalaprov.py -u usr:pwd -b http://myco.com:8080/ContentManager/ -n MyCo
            --build-netic --query-file OldPlayer --sync-time --restart-svc
'''
if True:            # initialize, enable folding
    import sys, os, logging, traceback, time, urllib2
    from os.path import join, dirname
    import scws
    try:
        from win32com.shell import shell, shellcon
        import scalalib as sl, scalatools as st
        import win32com.client
        _objWMIService = win32com.client.Dispatch('WbemScripting.SWbemLocator')
        _objSWbemServices = _objWMIService.ConnectServer('.', 'root\\cimv2')
        wmiquery = _objSWbemServices.ExecQuery
        import win32_unicode_argv
    except ImportError, e:
        print e
        print 'ERROR:  Required modules missing, install Python for Scala.'
        sys.exit(3)

    __version__             = '1.02'
    _def_interval           = 1 * 60  # 5 mins
    _def_timing             = (13, 1, 0)
    _def_loglevel           = 'info'
    _warn_on_tries          = 3
    _not_avail_msg          = 'NOT_AVAILABLE'
    _ex_authstr             = 'wsusr:pwd'
    _ex_network             = 'Company'
    _ex_baseurl             = 'http://myco.com:8080/ContentManager/'
    _svc_name               = 'ScalaNetClient5'
    _ERR_BASE               = 2
    _ERR_NET                = 3
    _ERR_AUTH               = 4
    _ERR_MISC               = 5

    # check for proxy settings, py env vars have an effect as well.
    _proxy_url = ''
    if st.get_regval(r'HKCU\Software\Microsoft\Windows' +
        r'\CurrentVersion\Internet Settings\ProxyEnable'):
        _proxy_url = st.get_regval(r'HKCU\Software\Microsoft' +
            r'\Windows\CurrentVersion\Internet Settings\ProxyServer')
        if ';' in _proxy_url:  # handle advanced... settings
            for purl in _proxy_url.split(';'):
                purl = purl.partition('=')
                if purl[0] == 'http':
                    _proxy_url = purl[2]; break
        _proxy_url = 'http://%s/' % _proxy_url

    _netic_templ = '''!ScalaScript500
// Created by Scala Provisioner (scalaprov.py), Version %(ver)s
{
    Optional Log.DaysToKeepLogs = 7;
    Optional Log.DetailsLevel = 1;
    Optional NETIC.AlertIfNotPlaying = On;
    Optional NETIC.BandwidthThrottle = 0;
    Optional NETIC.BandwidthThrottleWindowClose = "";
    Optional NETIC.BandwidthThrottleWindowOpen = "";
    Optional NETIC.ConnectThroughManualEntry = "";
    Optional NETIC.ConnectThroughPhonebookEntry = "";
    Optional NETIC.ConnectViaDialUp = 0;
    Optional NETIC.EnableProxy = %(enable_prx)s;
    Optional NETIC.FTPUsePassiveMode = Off;
    Optional NETIC.HangUpAfterIdleMinutes = 3;
    Optional NETIC.MinutesToWaitBeforeSendingAlert = 1;
    Optional NETIC.PlayerName = "%(player)s";
    Optional NETIC.PlayerUuid = "%(uuid)s";
    Optional NETIC.ProxyURL = "%(prx_url)s";
    Optional NETIC.RedialAttempts = 3;
    Optional NETIC.SecondsBetweenAttempts = 5;
    Optional NETIC.ServerBasePath = "%(baseurl)s";
    Optional NETIC.ServerNetworkName = "%(network)s";
    Optional NETIC.TransmissionFolder = "%(trans_fldr)s";
    Optional NETIC.TransmissionPollingInterval = 10;
}
'''
    _timing_templ = '''!ScalaScript500
// Created by Scala Provisioner (scalaprov.py), Version %(ver)s
{
    Optional DateFormat = %(datefmt)s;
    Optional TimeFormat = %(timefmt)s;
    Optional WeekdayFormat = %(weekdayfmt)s;
    Optional Timing.DefaultType = 0;
    Optional Timing.CalendarType = 0;
    Optional Timing.Uppercase = Off;
    Optional Timing.CustomTimeFormatString = "";
    Optional Timing.CustomDateFormatString = "";
}
'''


class _LogFilter(logging.Filter):
    'Demotes unimportant log messages.'
    def filter(self, record):
        allowit = True
        if record.funcName == 'get_ini':
            record.levelname = logging._levelNames[logging.DEBUG]
            if not _log.isEnabledFor(logging.DEBUG): allowit = False
        elif record.funcName == 'get_regval':
            record.levelname = logging._levelNames[logging.DEBUG]
            if not _log.isEnabledFor(logging.DEBUG): allowit = False
        elif (record.funcName.startswith('build_') and
            'backup' in record.msg):
            record.levelname = logging._levelNames[logging.DEBUG]
            if not _log.isEnabledFor(logging.DEBUG): allowit = False
        return allowit


def build_netic(outfname, endpoint='', plr_authstr='', player='',
    uuid='', network='', **extra):
    '''
        Builds the netic.sca file.
        Arguments:
            outfname        Output filename, use find_config() to find it.
        Options:
            endpoint        URL fragment containing host:port/path.
            plr_authstr     Scala Player credentials as a "user:pwd" string.
            player          Player's name.
            uuid            Identifier generated by Content Manager.
            network         Scala network.
        Note:
            Player passwords are not encrypted by this tool.
    '''
    ver = __version__
    baseurl = 'http://%s@%s' % (plr_authstr, endpoint)
    if not baseurl.endswith('/'): baseurl = baseurl + '/'
    enable_prx = ('On' if _proxy_url else 'Off')
    prx_url = _proxy_url
    trans_fldr = '%sdata/webdav/%s/plan/%s/plan.xml' % (baseurl, network, uuid)

    text = _netic_templ % locals()

    if _log.isEnabledFor(logging.DEBUG):
        _log.debug('netic.sca:\n' + text)
    try:    # Make a backup.  Only successful once, which is what we want.
        if os.path.exists(outfname):  os.rename(outfname, outfname + '.bak')
    except Exception, e:
        _log.warn('backup file already exists.  ' + str(e))
    outfile = file(outfname, 'w')
    outfile.write(text.encode('utf8'))
    outfile.close()
    _log.info('"%s" complete.', outfname)


def build_timing(outfname, datefmt=_def_timing[0], timefmt=_def_timing[1],
    weekdayfmt=_def_timing[2], **extra):
    '''
        Builds the timing.sca file.  Defaults to ISO descending datetime.
        Arguments:
            outfname        Output filename, use find_config().
        Options:
            datefmt         Date format as integer.
            timefmt         Time format as integer.
            weekdayfmt      Weekday format as integer.
    '''
    ver = __version__
    text = _timing_templ % locals()

    if _log.isEnabledFor(logging.DEBUG):
        _log.debug('timing.sca:\n' + text)
    try:    # Make a backup.  Only successful once, which is what we want.
        if os.path.exists(outfname):  os.rename(outfname, outfname + '.bak')
    except Exception, e:
        _log.warn('backup file may already exist.  ' + str(e))
    outfile = file(outfname, 'w')
    outfile.write(text)
    outfile.close()
    _log.info('complete.')


def find_config(filename='netic.sca'):
    '''
        Find path to the Scala config folder.  Handles mmos.ini root data
        folder modifications.
        Options:
            filename        Filename to join with with config folder, or '' for
                            bare folder.
        Returns:
            Path string with optional filename attached.
            None on error.
    '''
    import ConfigParser as cp
    netic_path = None
    try:  # mmos.ini first
        mmosini = st.get_ini(hint='player')     # throws AttributeError if st 1.00
        rootf = mmosini.get('WIN32_RootDataFolder'.lower()).replace('"','')
        if rootf:
            netic_path = join(rootf, 'Application Data', 'Config', filename)
        else:       raise AttributeError
    except (AttributeError, ImportError, cp.ParsingError):
        # look in All Users/Application Data
        appdataf = shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0)
        netic_path =  join(appdataf, 'Scala', 'InfoChannel Player 5', 'Config',
            filename)

    if not os.access(os.path.dirname(netic_path), os.W_OK):
        _log.critical('Not able to write netic.sca at "%s".' % netic_path)
        netic_path = None
    _log.debug('netic_path: "%s"', netic_path)
    return netic_path


def get_disk_sn():
    '''
        Retrieves the serial number of the first fixed disk.
        Returns:
            Serial number or not available string.
    '''
    snum, tag = '', ''
    try:
        results = wmiquery('Select * from Win32_PhysicalMedia')
        snum = results[0].SerialNumber
        tag  = results[0].Tag
    except IndexError:
        snum = _not_avail_msg
    _log.debug('Disk (%s) Serial Number: %s' % (tag, snum))
    return snum


def get_display_adapter_arch():
    '''
        Retrieves the vendor/architecture of the first video adapter.
        Returns:
            Name or not available string.
    '''
    try:
        results = wmiquery('Select * from Win32_VideoController')
        arch = results[0].AdapterCompatibility
        arch = arch.split()[0].upper().replace(',','').replace('.','')
    except IndexError:
        arch = _not_avail_msg
    _log.debug('Display adapter architecture: %s' % arch)
    return arch


def get_hw_serial():
    '''
        Retrieves hardware serial number from WMI or BIOS info.
        Returns:
            Serial number string.
            Blank string if not found.
    '''
    snum = ''
    try:
        results = wmiquery('Select * from Win32_ComputerSystemProduct')
        snum = results[0].IdentifyingNumber
        if not snum:
            results = wmiquery('Select * from Win32_BIOS')
            snum = results[0].SerialNumber
    except IndexError:
        snum = ''  # now falling back to MAC Address
    _log.debug('Hardware Serial Num from WMI: %s' % (snum or _not_avail_msg))
    return snum


def get_mac_address(wireless=False):
    '''
        Retrieves the MAC address of the first network adapter.
        Options:
            wireless        Include adapters described as wireless.
        Returns:
            Address string w/o delimiters, or not available message.
        Note:
            This function may be unreliable when there are multiple NICs.
            Their order is not guaranteed by the OS, and the addresses are
            changeable, could be disabled, etc.
    '''
    try:
        adapters = wmiquery('Select * from Win32_NetworkAdapterConfiguration')
        adapters = [ obj  for obj in adapters if (obj.IPEnabled) ]
        if not wireless:
            adapters = [  obj for obj in adapters
                          if ('wireless' not in obj.Description.lower())
            ]
        macs = [ obj.MACAddress.replace(':', '')  for obj in adapters ]
        mac = macs[0]
    except IndexError:
        mac = _not_avail_msg
    _log.debug('MAC Address: %s' % mac)
    return mac


def get_manufacturer():
    '''
        Retrieves the system manufacturer of the local system.
        Returns:
            Name or not available string.
    '''
    man, tag = '', ''
    try:
        results = wmiquery('Select * from Win32_ComputerSystem')
        man = results[0].Manufacturer
    except Exception:
        man = _not_avail_msg
    _log.debug('Manufacturer from WMI: %s' % man)
    return man


def get_monitor_res():
    '''
        This function attempts to retrieve the native hardware resolution of
        the first monitor returned by Windows.  It does this by looking for
        a connected monitor and then parsing its EDID information cached in
        the registry.
        Returns:
            Tuple containing, (W, H, Orientation)
            None on error.
        Note:
            If the resolution found is below 1024x768 it will be raised to
            that as a minimum fallback.
    '''
    import win32api as api, win32con as con, pywintypes
    res, curres, fsres = (0, 0), (0, 0), (1024, 768)
    dtd = 54  # start byte of detailed timing desc.
    try:  # preserve current settings, orientation of first display
        devmode = api.EnumDisplaySettings(None, con.ENUM_CURRENT_SETTINGS)
        res = (devmode.PelsWidth, devmode.PelsHeight)  # may differ bc of setup
        orient = devmode.DisplayOrientation
        _log.debug('Current display orientation from Win32api: %s' % orient)
    except pywintypes.error:
        orient = 0
    try:  # get PNP id to find EDID in registry
        for monitor in wmiquery('Select * from Win32_DesktopMonitor'):
            # http://msdn.microsoft.com/en-us/library/aa394122%28VS.85%29.aspx
            if monitor.Availability in (3, 7, 13, 14, 15, 16): # connected
                curres = (monitor.ScreenWidth, monitor.ScreenHeight)
                _log.debug('Current monitor resolution from WMI: %s' % (curres,))
                regkey = ('HKLM\\SYSTEM\\CurrentControlSet\\Enum\\' +
                    monitor.PNPDeviceID + '\\Device Parameters\\EDID')
                edid = st.get_regval(regkey)
                if edid:
                    _log.debug('EDID Version: %s.%s' % (edid[18], edid[19]))
                    # upper nibble of byte x 2^8 combined with full byte
                    hres = ((edid[dtd+4] >> 4) << 8) | edid[dtd+2]
                    vres = ((edid[dtd+7] >> 4) << 8) | edid[dtd+5]
                    _log.debug('EDID DTD0: ' + str((hres, vres)))
                    res = (hres, vres)
                    break  # give up on first success
                else:
                    raise RuntimeError, 'EDID not found in registry'
    except RuntimeError, e:
        _log.error('%s.' % e)
    except Exception, e:
        _log.error('%s:\n  %s' % (e.__class__.__name__, traceback.format_exc()) )

    # sanity checking
    if res[0] >=  res[1]:   monorient = 'landscape'  # monitor, not display
    else:                   monorient = 'portrait'
    if monorient == 'landscape':
        if (res[0] < fsres[0]) or (res[1] < fsres[1]):
            res = fsres
            _log.warning('Raising resolution to minimum: %s' % res)
    else:
        if (res[1] < fsres[0]) or (res[0] < fsres[1]):
            res = (fsres[1], fsres[0])
            _log.warning('Raising resolution to minimum: %s' % res)
    if curres == res:
        _log.warn('Leaving resolution unchanged (settings match or missing).')
        return None
    else:
        return res + (orient,)


def get_plr_vers():
    '''
        Retrieves the version of the Scala Player software from the Registry.
        Returns:
            version string or None if not found.
    '''
    key = r'HKLM\SOFTWARE\Scala\InfoChannel Player 5\ProductVersion'
    try:
        value = st.get_regval(key)
    except:
        value = None
    return value


def get_server_datetime(url, interval=_def_interval, tries=5):
    '''
        Poor Man's NTP Sync; asks for the Date header from an HTTP Server.

        Arguments:
            url             URL to perform a HEAD request on.
        Returns:
            Date string compatible with set_datetime() (RFC2822).
        Options:
            interval        On error, how long to wait in secs to try again.
            tries           On error, how many attempts before giving up.
    '''
    import httplib
    from urlparse import urlparse
    headers = {'Pragma':'no-cache', 'Cache-Control':'no-cache'}  # disallow caching
    parsed = urlparse(url)
    conn = httplib.HTTPConnection(parsed.netloc)
    conn.request('HEAD', parsed.path, headers=headers)

    while tries:
        try:
            response = conn.getresponse()
            if response:
                if not response.status == 200:
                    _log.warn('%s %s', response.status, response.reason)
                datestr = response.getheader('Date', '')
                if datestr:
                    _log.info(datestr)
                    return datestr
        except (urllib2.URLError, urllib2.HTTPError, IOError), e:
            _log.error('%s: %s' % (e.__class__.__name__, e) )
            if tries > _warn_on_tries:
                _log.warn('Unable to contact server.  Will try again in %i minutes.'
                     % (interval/60))

        _log.info( 'Sleeping %i minutes (%.01f hours)...' % (interval/60, interval/3600.0) )
        time.sleep(interval)
        tries = tries - 1


def get_vnc_hash(password):
    '''
        Given a password, return a UltraVNC compatible hash from its first
        eight chars.
        Arguments:
            password
        Returns:
            hash string.
        Requires:
            d3des module to be available.
            http://vnc2flv.googlecode.com/svn-history/r2/trunk/vnc2flv/vnc2flv/d3des.py
    '''
    hashstr = None
    try:
        import d3des as d
    except ImportError:
        _log.warn('Hash algorithm module not found, skipping VNC password set.')
    else:
        passpadd = (password + '\x00'*8)[:8]
        strkey = ''.join([ chr(x) for x in d.vnckey ])
        ekey = d.deskey(strkey, False)

        hashed = d.desfunc(passpadd, ekey)
        hashstr = hashed.encode('hex')
        _log.info('VNC password hash: ' + hashstr)
    return hashstr


def player_create(name, baseurl, authstr, query=True, desc='', enabled=True):
    '''
        Creates a Player object in Content Manager, with the given name.
        Arguments:
            name            Player name
            baseurl         Base URL to Content Manager
            authstr         "user:pwd" credential string.
            query           Switch to player_query() if Player object already exists.
            enabled         Player is allowed to download and run content.
        Returns:
            Player's Transfer Objec on success.
            None on failure, e.g. if query=False and Player already exists.
    '''
    cm = scws.ConManager(baseurl, authstr)
    try:
        pto = dict(name=name)
        if desc:  pto['description'] = desc
        pto['enabled'] = enabled
        players = cm.player.create(player=pto)
        if players:
            return players[0]
    except ValueError:
        _log.warn('Switching to Player webservice query to find details.')
        if query:
            return player_query_ws(name, baseurl, authstr)
    except Exception:
        _log.critical('Unable to continue.')
        sys.exit(_ERR_MISC)


def player_query_ws(name, baseurl, authstr):
    '''
        Query Content Manager via Webservice for an existing Player object by name.
        Arguments:
            name            Player name
            baseurl         Base URL to Content Manager
            authstr         "user:pwd" webservice (not Player) credential string.
        Returns:
            Player's Transfer Object on success.
            None on failure.
    '''
    cm = scws.ConManager(baseurl, authstr)

    src = dict(column='name', restriction='EQUALS', value=name)
    players = cm.player.list(searchCriteria=src)
    if players:
        return players[0]
    else:
        _log.critical('Player %s not found.' % name)
        sys.exit(_ERR_MISC)


def player_query_file(name, baseurl, authstr, network):
    '''
        Query Content Manager for an existing Player object by name.
        Arguments:
            name            Player name, must be enabled in CM.
            baseurl         Base URL to Content Manager
            authstr         "user:pwd" Player (not webservice) credential string.
            network         CM network.
        Returns:
            Player Object on success.
            None on failure.
    '''
    import xml.etree.ElementTree as et

    url = join(baseurl, 'data/webdav', network, 'redirect.xml')
    url = url.replace('\\', '/')
    user, pwd = authstr.split(':', 1)
    filename = 'player_list.xml'

    try:
        st.grab_url(url, filename=filename, username=user, password=pwd)
        filename = st.find_file(filename)
    except Exception, e:
        _log.critical('Unable to retrieve player details from CM. ' + str(e))
        sys.exit(_ERR_MISC)

    # parsen-sie
    xmldat = et.parse(filename).getroot()
    players = xmldat.findall('player')
    players = dict([    (player.findtext('name'), player.findtext('uuid'))
                        for player in players ])
    try:    # return in same format as scws calls
        return scws.TObj(name=name, uuid=players[name])
    except KeyError, e:
        _log.critical('Player details not found for %s.  Is it enabled?' % name)
        sys.exit(_ERR_MISC)


def player_add_group(plr, group, baseurl, authstr):
    '''
        Add Player object to Group by name.
        Arguments:
            plr             Player Transfer Object or dict, e.g.: {'id': 123}
            group           Group name.
            baseurl         Base URL to Content Manager
            authstr         "user:pwd" credential string.
        Returns:
            True on success.
            None on failure.
    '''
    cm = scws.ConManager(baseurl, authstr, api_vers='v1.2')

    src = dict(column='name', restriction='EQUALS', value=group)
    try:
        groups = cm.player.listPlayerGroups(searchCriteria=src)
        if groups:
            cm.player.addPlayerGroup(dict(playerId=plr.id),
                playerGroupId=groups[0].id)
            return True
        else:
            _log.error('Group %s not found.' % group)
    except Exception:
        pass


def player_set_channel(plr, channel, baseurl, authstr):
    '''
        Assign a Player object's first display to a channel found by name.
        Arguments:
            plr             Player Transfer Object or dict, e.g.: {'id': 123}
            channel         Channel name.
            baseurl         Base URL to Content Manager
            authstr         "user:pwd" credential string.
        Returns:
            True on success.
            None on failure.
    '''
    cm = scws.ConManager(baseurl, authstr)

    src = dict(column='name', restriction='EQUALS', value=channel)
    try:
        # get channel ids
        channels = cm.channel.list(searchCriteria=src)
        if not channels:
            _log.error('Channel %s not found.' % channel)
            return

        displays = cm.player.getPlayerDisplays(playerId=plr.id)
        if displays:
            cm.player.updatePlayerDisplay( playerDisplay=
                dict(id=displays[0].id, channelId=channels[0].id,
                screenCounter=1) )
            return True
        else:
            displays = cm.player.addPlayerDisplay( playerId=plr.id,
                playerDisplay=dict(channelId=channels[0].id, screenCounter=1) )[0]
            if displays:
                cm.player.updatePlayerDisplay( playerDisplay=
                    dict(id=displays[0].id, channelId=channels[0].id,
                    screenCounter=1) )
                return True
            else:
                _log.error('Unable to create display/set channel.')
                return

    except Exception:
        pass


def _run(command, commun=True):
    'Execute a command line.'
    from subprocess import PIPE, Popen as popen
    output = ''
    try:
        if commun:
            p = popen(command, stdout=PIPE)
            output = p.communicate()[0]
        else:
            p = popen(command)
    except WindowsError, e:
        _log.error('Windows Error: %s', str(e))
        raise
    if commun: _log.info('response: \'%s\' ' % output.strip())


def set_timezone(name):
    '''
        Sets the system timezone.
        Arguments:
            name            The Windows compatible name of a timezone, e.g.
                                "Pacific Standard Time".
        Note:
            Daylight variations of timezones aren't accepted.  The correct
            offset will be selected automatically.
    '''
    if sys.getwindowsversion()[0] == 5:
        cmd = 'control.exe TIMEDATE.CPL,,/Z ' + name
    else:
        cmd = 'tzutil /s "%s"' % name

    _log.debug('running: \'%s\'', cmd)
    _log.info('complete.')
    _run(cmd, commun=False)


def set_datetime(datestr):
    '''
        Given a date string, set Windows System date/time.
        Arguments:
            datestr         RFC2822 (Section 3.3) format date string:
                            http://tools.ietf.org/html/rfc2822#section-3.3
                            most easily retrieved from get_server_datetime().
        Example:
            set_datetime('Wed, 26 Oct 2011 16:03:20 GMT')
    '''
    from email.utils import parsedate_tz, mktime_tz
    import win32api
    parsed = parsedate_tz(datestr)              # parse with timezone
    if parsed:
        timestamp = mktime_tz(parsed)           # 2 utc timestamp seconds
        time_utc = time.gmtime( timestamp )     # 2 utc tuple
        try:
            win32api.SetSystemTime(
                time_utc[0], # year,
                time_utc[1], # month ,
                ((time_utc[6] + 1) % 7), # dayOfWeek conversion,
                time_utc[2], # day ,
                time_utc[3], # hour ,
                time_utc[4], # minute ,
                time_utc[5], 0) # second , ms
        except Exception, e:
            _log.error(str(e))
        _log.debug('%s (UTC)' % time_utc)
        _log.info('complete.')
    else:
        _log.error('Datestring "%s" not able to be parsed.  System time not set.')


def set_display(width, height, orient=0, depth=32, hz=60):
    '''
        Attempts to set the display settings to given parameters.  If
        valid, they will take hold at next boot.
        Arguments:
            width           Resolution in pixels, as integer.
            height
        Options:
            orient          Orientation, 0:std, 1:90 deg, 2:180, 3:270.
            depth           Color depth.
            hz              Refresh rate in cycles/second.
        Note:
            The combination chosen may not be available; an error will be logged.
    '''
    import win32api as api, win32con as con, pywintypes
    retvals = dict( (getattr(con, c), c)    for c in dir(con) # get names
                                            if c.startswith('DISP_') )
    def get_display_modes():
        display_modes = {}
        n = 0
        while True:
            try:  devmode = api.EnumDisplaySettings(None, n)
            except pywintypes.error:  break
            else:
                key = (
                  devmode.BitsPerPel,
                  devmode.PelsWidth,
                  devmode.PelsHeight,
                  devmode.DisplayFrequency,
                  devmode.DisplayOrientation
                )
                display_modes[key] = devmode
                n += 1
        return display_modes

    if orient in (0, 2):  # landscape
        mode_requested = (depth, width, height, hz, orient)
    else:                 # portrait
        mode_requested = (depth, height, width, hz, orient)
    _log.info('Attempting to set display resolution to: %s; deferred until ' +
        'next boot.', (width, height, orient, depth, hz))
    devmode = get_display_modes().get(mode_requested)
    if (devmode and
        api.ChangeDisplaySettings(devmode, con.CDS_TEST) == 0):  # check first
        r = api.ChangeDisplaySettings(devmode,     # defer until next boot
            con.CDS_UPDATEREGISTRY | con.CDS_NORESET | con.CDS_GLOBAL)
        _log.debug('win32api.ChangeDisplaySettings() returned: %s' %
            retvals.get(r, r) )
    else:
        _log.error('Display mode %s not supported.' % (mode_requested,))


if __name__ == '__main__':                      # Run from command line
    from optparse import OptionParser

    parser = OptionParser(usage=__doc__, version=__version__)
    parser.add_option('-a', '--authstr', metavar="U:P",
        help='CM webservice auth string, e.g. "%s"' % _ex_authstr)
    parser.add_option('-b', '--baseurl', metavar='URL',
        help='Base URL destination to Content Manager, e.g. "%s"' % _ex_baseurl)
    parser.add_option('-n', '--network',
        metavar='NET', help='CM network, e.g. "%s"' % _ex_network)

    parser.add_option('-c', '--create', metavar='NAME',
        help='Create Player Object in Content Manager and return its UUID.  See -q.')
    parser.add_option('-C', '--channel', metavar='NAME',
        help='Configure Channel for Player in CM.')
    parser.add_option('-d', '--set-display', metavar='W,H[,O,D,Hz]',
        help='Attempt to manually set system display to a specific res/orient.'+
        ' e.g. 1280,768,0,32,60')
    parser.add_option('-D', '--auto-display', action='store_true',
        help='Attempt to set system display to first monitor\'s native resolution.')
    parser.add_option('--desc', metavar='STR', default='',
        help='Add description to CM Player object (create only).')
    parser.add_option('-g', '--group', metavar='G',
        help='Add CM Player object to group.')
    parser.add_option('-q', '--query-ws', metavar='NAME',
        help='Query CM webservice for an existing Player Obj. by name.' +
        ' Requires webservice auth (-a), not Player auth (-u).')
    parser.add_option('-Q', '--query-file', metavar='NAME',
        help='Query CM redirect.xml for an existing Player Obj. by name.' +
        ' Requires Player auth (-u) if non-default, not webservice auth (-a).')
    parser.add_option('-r', '--restart-svc', action='store_true',
        help='Restart the Scala Transmission Client (netic service) when complete.')
    parser.add_option('-s', '--sync-time', action='store_true',
        help='Sync Player datetime with Content Manager (Poor Man\'s NTP). Req: -b')
    parser.add_option('-u', '--plr-authstr', metavar='U:P',
        help='Manually set Player user/pwd in netic.sca or , else default.')
    parser.add_option('-z', '--timezone', metavar='TZ',
        help='Set Player timezone (not "Daylight"), e.g. "Pacific Standard Time".')

    parser.add_option('-N', '--build-netic', action='store_true',
        help='Build a new netic.sca file using details from CM Player Object.')
    parser.add_option('-T', '--build-timing', metavar='D,T,W',
        help='Build a new timing.sca file, pass datefmt, timefmt, weekdayfmt'
        + ' as integers, e.g. 13,1,0')

    parser.add_option('-V', '--very-verbose', action='store_true',
        help='Enable verbose diagnostic output.')
    (opts, args) = parser.parse_args()

    # set up logging
    print
    _loglevel = _def_loglevel
    if opts.very_verbose:   _loglevel = 'debug'
    _log = sl.get_logger(level=_loglevel, format='  %(levelname)-8.8s %(funcName)s: %(message)s')
    for handler in _log.handlers:
        handler.addFilter(_LogFilter())
    _log.info('Scala Provisioner, version %s (-h for help).' % __version__)
    _log.debug('Proxy config from registry: %s' % _proxy_url)

    # validate
    if opts.build_netic:
        if not opts.baseurl:
            _log.critical('Baseurl option is required.')
            sys.exit(_ERR_BASE)
        if not opts.network:
            _log.critical('Network option is required.')
            sys.exit(_ERR_NET)
        if not (opts.authstr or opts.plr_authstr):
            _log.critical('Authstr option is required.')
            sys.exit(_ERR_AUTH)
        if not (opts.create or opts.query_ws or opts.query_file):
            _log.critical('--build-netic requires --create or --query-*')
            sys.exit(_ERR_MISC)

        if opts.plr_authstr:
            if opts.plr_authstr.count(':') != 1:
                _log.critical('--plr-authstr requires "user:pwd"')
                sys.exit(_ERR_MISC)
        else:
            opts.plr_authstr = 'player_%s:scala' % opts.network
    else:
        if opts.plr_authstr:
            _log.warn('-N/--build-netic required for user/pwd set.')

    if opts.create and (opts.query_ws or opts.query_file):
        _log.warn('--create and --query used together, query overrides.')

    if opts.sync_time and not opts.baseurl:
        _log.critical('Baseurl option is required with --sync-time.')
        sys.exit(_ERR_BASE)

    if opts.group and not (opts.create or opts.query_ws or opts.query_file):
        _log.critical('--group requires --create or --query-*.')
        sys.exit(_ERR_MISC)
    if opts.channel and not (opts.create or opts.query_ws or opts.query_file):
        _log.critical('--channel requires --create or --query-*.')
        sys.exit(_ERR_MISC)
    if opts.desc and not opts.create:
        _log.critical('--desc requires --create.')
        sys.exit(_ERR_MISC)

    # execute
    plr = None
    try:
        if opts.create:
            plr = player_create(opts.create, opts.baseurl, opts.authstr,
                desc=opts.desc)

        if opts.query_ws:
            plr = player_query_ws(opts.query_ws, opts.baseurl, opts.authstr)

        if opts.query_file:
            plr = player_query_file(opts.query_file, opts.baseurl, opts.plr_authstr, opts.network)

        if opts.group:
            player_add_group(plr, opts.group, opts.baseurl, opts.authstr)

        if opts.channel:
            player_set_channel(plr, opts.channel, opts.baseurl, opts.authstr)

        if opts.build_netic:

            filename = find_config()
            endpoint = opts.baseurl.partition('//')[2]
            if filename:
                build_netic(filename, player=(opts.query_ws or opts.create),
                    endpoint=endpoint, uuid=plr.uuid, network=opts.network,
                    plr_authstr=opts.plr_authstr)

        if opts.build_timing:
            filename = find_config('timing.sca')
            if filename:
                args = [ int(x) for x in opts.build_timing.split(',') ]
                build_timing(filename, *args)

        if opts.timezone:
            set_timezone(opts.timezone)

        if opts.sync_time:
            dt = get_server_datetime(opts.baseurl)
            set_datetime(dt)

        if opts.auto_display:
            args = get_monitor_res()
            if args:
                set_display(*args)

        if opts.set_display:
            args = [ int(x) for x in opts.set_display.split(',') ]
            if len(args) < 2:
                _log.error('set_display: at least two args required.')
            else:
                set_display(*args)

        if opts.restart_svc:
            try:
                st.restart_svc(_svc_name)
            except AttributeError:
                _log.error('full service restart requires scalatools 1.45+')
            _log.info('Done.')
        else:
            if opts.build_netic:
                _log.info('Done.  Local changes will not take effect until service restart.')
            else:
                _log.info('Done.')
    except Exception:
        _log.error(traceback.format_exc())

else:
    _log = sl.get_logger(level=_def_loglevel)



