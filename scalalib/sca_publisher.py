'''
    sca_publisher.py - (C) 2009-2010 Scala, Mike Miller, Guillaume Proux
    Publish Scala Scripts to a Content Manager from the command line.

    Command line usage:
        %%prog <-t URL> [options] [files*] [folders]

    Returns the following exit status codes:
        0       - success
        %s       - no files given
        %s       - no target dest given
        %s       - Error during upload encountered.
        %s       - Killed by Ctrl-C.
'''
if True:  # initialization
    import sys, os.path, time, msvcrt
    from optparse import OptionParser
    from glob import glob
    import pythoncom
    import scalalib as sl

    __version__ = '1.13'
    ex_url = 'http://user:passwd@mycm.com:8080/ContentManager?NET'
    status = {}
    pollfreq = 3
    ERR_FILE    = 1     # error codes
    ERR_DEST    = 2
    ERR_UPLD    = 5
    ERR_KILL    = 6
    opts = args = log = verbose = None

def setup():
    global opts, args, log, verbose
    parser = OptionParser(usage=__doc__
        % (ERR_FILE, ERR_DEST, ERR_UPLD, ERR_KILL), version=__version__)
    parser.add_option('-e', '--editpassword', metavar='PASS', default='',
        help='Optional edit-password to apply to published script(s).')
    parser.add_option('-l', '--logfname', metavar='FN', default='',
        help='A filename to log progress to.  Default: "%TEMP%/pub_log.txt"')
    parser.add_option('-o', '--options', metavar='ST', default='',
     help='''A string containing zero or more of the following option flags:
 "d": Show progress GUI,
 "i": Ignore errors (scripts get published with errors),
 "f": Do NOT include fonts,
 "w": Do NOT include wipes,
 "x": Skip cleanup,
 "p": Use passive FTP''')
    parser.add_option('-s', '--subfolder', metavar='F', default='',
        help='Subfolder into which to publish.')
    parser.add_option('-t', '--targeturl', metavar='URL',
        help='Publish destination as UNC/FTP/HTTP(S).  e.g.:\n"%s"' % ex_url)
    parser.add_option('-v', '--verbose', action='store_true',
        help='Enable verbose output.')
    parser.add_option('-V', '--very-verbose', action='store_true',
        help='Enable debugging output.')
    (opts, args) = parser.parse_args()

    # start logging
    log = sl.get_logger(level=  'debug' if opts.very_verbose else
                                ('info'  if opts.verbose else 'warn') )
    log.debug('options: %s | script args: %s' % (opts.__dict__, args) )
    verbose = opts.verbose or opts.very_verbose

    # validate arguments
    if not args:
        parser.print_help(); print
        log.error('a file or folder to publish missing.')
        sys.exit(ERR_FILE)

    if not opts.targeturl:      # "required options"  :/
        parser.print_help(); print
        log.error('-t, --targeturl, must be specified.')
        sys.exit(ERR_DEST)

def main():
    'Get list of files and upload.'
    log.debug( '%s v%s  scalalib:v%s' % (sys.argv[0], __version__,
        sl.__version__) )

    # create script list
    scripts = []
    for filespec in args:
        results = []
        if ('*' in filespec) or ('?' in filespec):
            results = glob(filespec)
        else:
            if os.path.exists(filespec):
                results = [filespec]

        for result in results:
            if os.path.isdir(result):
                scripts += glob(result + '/*.sca')
            else:
                scripts.append(result)

    if not scripts:
        log.error('No Script files found.')
        sys.exit(ERR_FILE)

    if len(scripts) > 4:    # warn on large number of scripts
        log.warn('About to publish: \n    %s' % scripts)
        print '\n\nHit any key to continue ... Ctrl-C to exit.',
        msvcrt.getch()

    try:
        pubhandle = sl.publish(scripts, opts.targeturl, targetfolder=opts.subfolder,
            logfilename=opts.logfname, editpassword=opts.editpassword,
            options=opts.options, autostart=True)

        log.debug('pubhandle is %s' % pubhandle)
        if pubhandle:
            if not verbose:
                print 'Publishing operation initiated ...'
            while True:  # run at least once
                time.sleep(pollfreq)
                status = sl.publish_check(pubhandle)
                statstr = ('Publishing script %(currentscriptnum)s of %(numberofscripts)s'
                    + ' - %(overallpercentdone)3.3s%% complete,  %(currentscriptname)s ')
                log.info(statstr % status)
                if status.get('overallpercentdone') == 100 or not verbose: break
            if status.get('allerrors'):
                for line in status.get('allerrors').split('\n'):
                    if line and not line.isspace():  log.error(line)
        elif pubhandle == None:
            log.critical('No publishing operation started.  Cannot continue.')

    except KeyboardInterrupt:
        log.warn('Killed by Ctrl-C.')
        return ERR_KILL
    except pythoncom.com_error, e:
        log.error(str(e))
        return ERR_UPLD


if __name__ == "__main__":
    setup()
    sys.exit(main())

