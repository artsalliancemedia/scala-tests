#!/usr/bin/env python
'''
    cm_upload.py - (C) 2008-2010 Scala, Mike Miller
    Uploads files to a Content Manager.

    Command line usage:
        %%prog <-d URL> <-n NET> <-a STR> [options] <filenames>

    Returns the following exit status codes:
        0        - success
        %s       - no files given
        %s       - no dest given
        %s       - no network given
        %s       - no authstr given
        %s       - Error during upload encountered.
'''
if True:  # initialization
    import sys
    import soaplib
    import scws
    from optparse import OptionParser
    import win32_unicode_argv

    # set up a few default variables first
    __version__     = '1.14'
    _ex_authstr     = 'scalaweb:pword'
    _ex_network     = 'Company'
    _ex_baseurl     = 'http://cm.myco.com:8080/ContentManager/'

    ERR_FILE    = 1     # error codes
    ERR_DEST    = 2
    ERR_NET     = 3
    ERR_AUTH    = 4
    ERR_UPLD    = 5
    ERR_KILL    = 6
    opts = args = log = None


def setup():
    'Parse the command line, and make sure output path is ready.'
    global opts, args, log
    parser = OptionParser(usage=__doc__
        % (ERR_FILE, ERR_DEST, ERR_NET, ERR_AUTH,ERR_UPLD), version=__version__)
    parser.add_option('-a', '--authstr', metavar="STR",
        help='Authorization string, e.g. "%s"' % _ex_authstr)
    parser.add_option('-b', '--baseurl', metavar='URL',
        help='Base URL destination to Content Manager, e.g. "%s"' % _ex_baseurl)
    parser.add_option('-d', '--dest', metavar='URL',
        help='Deprecated.  Use -b instead.')
    parser.add_option('-n', '--network',
        metavar='NET', help='CM network, e.g. "%s"' % _ex_network)
    parser.add_option('-s', '--subfolder', metavar='STR',
        help='Upload to this subfolder.')
    parser.add_option('-t', '--upload-type', metavar='STR', default='auto',
        help='Force upload type.  MEDIA, MAINTENANCE.  Default: AUTO.')
    parser.add_option('-v', '--verbose', action='store_true',
        help='Enable verbose output of the upload process.')
    parser.add_option('-V', '--very-verbose', action='store_true',
        help='Enable verbose debugging output of the HTTP/SOAP protocol.')

    (opts, args) = parser.parse_args()
    if not args:
        parser.print_help()
        sys.exit(ERR_FILE)

    # set up a logging channel
    import scalalib
    loglevel = 'warn'
    if opts.verbose:        loglevel = 'info'
    if opts.very_verbose:   loglevel = 'debug'
    log = scalalib.get_logger(level=loglevel)

    # validate arguments
    if not (opts.dest or opts.baseurl):       # "required options"  :/
        log.error('Baseurl is required.')
        sys.exit(ERR_DEST)
    elif (not opts.baseurl) and opts.dest:
        log.warn('Dest is deprecated, use -b/--baseurl')
        opts.baseurl = opts.dest
    if not opts.network:
        log.error('Network is required.')
        sys.exit(ERR_NET)
    if not opts.authstr:
        log.error('Authstr is required.')
        sys.exit(ERR_AUTH)

def main():
    ' Get list of files and upload.'
    log.debug('%s v%s  scws:v%s  soaplib:v%s' % (sys.argv[0], __version__,
        scws.__version__, soaplib.__version__))
    cm = scws.ConManager(opts.baseurl, opts.authstr)   # Create a CM object
    Errors = None

    for filename in args:
        try:
            if not opts.verbose or opts.very_verbose:
                print 'uploading: ', filename, '... ',
                sys.stdout.flush()
            fileIds = cm.upload_file(filename, opts.network,
                subfolder=opts.subfolder, upload_method='PUT',
                upload_type=opts.upload_type)
            log.info('uploaded %s' % filename)
            if not opts.verbose or opts.very_verbose:
                print 'Done.'
        except KeyboardInterrupt:
            log.warn('Killed by Ctrl-C.')
            return ERR_KILL
        except Exception:
            Errors = True

    if Errors:
        return ERR_UPLD


if __name__ == "__main__":
    setup()
    sys.exit(main())
