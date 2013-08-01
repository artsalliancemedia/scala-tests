'''
    soaplib.py - (C) 2007-2010 Scala, Mike Miller
    A library to handle SOAP XML RPC in simple cases.
    Todo:
        - Reduce repetitive code.
        - Used httplib for historical reasons; upgrade to urllib2
'''
if True:  # set up
    import os, sys
    import httplib, base64, urllib, urlparse
    import logging
    try:
        import scalalib as sl
        import scalatools as st     # check for fileLogger support
    except ImportError:
        sl = st = None

    __version__ = '1.15'
    __all__ = ['dict2xml', 'get', 'put', 'post', 'xml2list', 'xml2dict']
    chunked_limit = 16384
    usr_agnt = 'Python/%s httplib' % sys.version.split()[0]
    soap_envelope = u'''<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Body>
            <%(function)s %(xmlns)s>
                %(argtext)s
            </%(function)s>
        </soap:Body>
    </soap:Envelope>
    '''
    loggername = 'scalalib.' + __name__
    log = logging.getLogger(loggername)
    if sl and hasattr(sl, '_nullh'):    # if not available or old vers
        log.addHandler(sl._nullh)       # quiet "no handler" error messages



# Functions
# ---------------------------------------------------------------------
def _find_et():
    ' Find the best installed Element Tree.'
    try:                        import xml.etree.cElementTree   as et
    except ImportError:
        try:                    import xml.etree.ElementTree    as et
        except ImportError:
            try:                import cElementTree             as et
            except ImportError:
                try:            import elementtree.ElementTree  as et
                except ImportError:
                    raise Exception, 'ImportError: ElementTree not found.'
    return et
et = _find_et()


def dict2xml(d, indent=4, envelope=''):
    'Given a python dictionary, return an indented XML-string representation.'

    if type(d) != dict:
        raise TypeError('Value is not a dictionary: %s' % d )

    tab = '    '
    spacing = tab * indent

    # handle start tag
    if envelope:    result = '%s<%s>\n' % (spacing, envelope)  # start tag
    else:           result = ''

    # handle enclosed tags
    keys = d.keys(); keys.sort()
    for i, key in enumerate(keys):
        spacing = tab * indent
        if envelope:
            spacing += tab

        valtype = type(d[key])
        if valtype is dict:    # TO is a dict, run it again
            result += dict2xml( d[key], envelope=key )
        elif valtype is list:  # if array, expand it
            for j, listitem in enumerate( d[key] ):
                if not envelope:
                    if j == 0:  spacing = ''
                    else:       spacing = tab * indent
                result += '%s<%s>%s</%s>\n' % (spacing, key, listitem, key)
        else:
            result += '%s<%s>%s</%s>\n' % (spacing, key, d[key], key)

    # handle end tag
    spacing = tab * indent
    if envelope:    result += '%s</%s>\n' % (spacing, envelope)   # end tag
    return result


def nodes2dict(parentnode):
    'Given XML nodes, return a dictionary, or dict of dicts.'
    result = {}
    count = 1
    numdigits = 0

    children = parentnode.getchildren()
    result['_typestr'] = parentnode.tag  # keep track of the parent name
    for node in children:

        tag = node.tag
        if '}' in tag:  tag = tag.split('}', 1)[-1]  # remove {namespace}

        if tag in result:  # avoid key collisions in dicts by padding
            if not numdigits: numdigits = len( str(len(children)) )
            tag = '%%s.%%0%sd' % numdigits % (tag, count)
            count += 1

        if node.getchildren(): # careful! - node not found, or node has no subnodes"
            result[tag] = nodes2dict(node)
        else:
            result[tag] = node.text
    return result


def nodes2list(nodes):
    'Given XML nodes, return a list of dictionaries.'
    results = []

    children = nodes.getchildren()
    for node in children:
        if node.getchildren():
            results.append( nodes2dict(node) )      # for TO's
        elif node.text:
            results.append( {node.tag:node.text} )  # for single tag responses
        # else pass
    return results


def xml2dict(xmltext, roottag):
    'Given XML, return dictionaries representing the structure.'

    searchstr = './/%s' % roottag
    nodes = et.fromstring(xmltext).find(searchstr)  # create etree
    if nodes:   return nodes2dict(nodes)
    else:       return None


def xml2list(xmltext, roottag):
    'Given an XML object representation, return a list of dictionary objects'

    searchstr = './/%s' % roottag
    nodes = et.fromstring(xmltext).find(searchstr)  # create etree
    if nodes:   return nodes2list(nodes)
    else:       return []


def handle_url(url, encoding='utf8'):
    'Given an url, return the host and path.'
    tup = urlparse.urlsplit(url)
    proto, host, path = tup[0], tup[1], tup[2]
    if not proto.lower() in ('http', 'https'):
        raise Exception, 'Protocol not supported: ' + proto
    path = urllib.quote(path.encode(encoding), safe='/%')  # can't handle uni
    return proto.lower(), host, path


def get(url, addheaders=None, authstr='', debug=False):
    'Convenience function to GET a file from an HTTP server. Use urlopen instead.'
    return _http_call('GET', url, addheaders, authstr, '', debug)


def put(filename, url, authstr='', chunked=True, debug=False):
    '''
        PUT a file to an HTTP server.
        Arguments:
            chunked         enable chunked transfer on larger files.
    '''
    # decide whether to send file chunked
    clen = os.path.getsize(filename)
    if chunked and clen > chunked_limit:    chunked = True
    else:                                   chunked = False
    addheaders = [ ('Content-Length', str(clen)) ]
    if chunked: addheaders.append( ('Transfer-Encoding', 'chunked') )

    # send file
    dataf = file(filename, 'rb')                # throws IOError if issue
    if chunked:     # Chunked transfer encoding, acceptance required by HTTP 1.1
        def body(http_conn):
            while True:
                bytes = dataf.read(8192)
                if not bytes: break
                length = len(bytes)
                http_conn.send('%X\r\n' % length)
                if debug:
                    http_conn.set_debuglevel(0)     # mask data send
                    print '<filedata>'
                http_conn.send(bytes + '\r\n')
                if debug:   http_conn.set_debuglevel(1)
            http_conn.send('0\r\n\r\n')
    else:
        body = dataf

    response = _http_call('PUT', url, addheaders, authstr, body, debug)
    dataf.close()
    return response


def post(url, addheaders=None, authstr='', body='', parameters='', filename='',
    function='', xmlns='', soapargs=None, debug=False):
    '''
        Executes an HTTP POST call against a web server.  Supports queries from
        form data, file upload, and SOAP calls.

        Arguments:
            url             - The network location.
        Options:
            Query with form data:
                parameters  - An un-encoded query string, e.g: "n1=v1&n2=v2"

            File upload:
                filename    - An existing absolute or relative file path.
                              Beware of large files, entire file loaded into mem.

            For a SOAP POST, use these options:
                function    - Name of the remote function to append. (req)
                xmlns       - XML namespace string (req)
                soapargs    - A list of dictionaries/objects to convert to XML.

            Generic POST:
                addheaders  - List of (name, value) tuples to include as headers.
                authstr     - String to encode for HTTP Basic authentication,
                                e.g.:  '<username>:<password>'
                body        - Data to send.  Do not use with SOAP, query, or
                                file upload options in the previous section.
                debug       - Enable to log verbose transport information.
        Returns:
            status, reason, body, ctype - tuple
    '''
    # check parameters
    if addheaders is None: addheaders = []
    if soapargs is None:   soapargs = []
    if function or xmlns or soapargs:   # posting a SOAP msg
        if not function or not xmlns:
            raise TypeError, 'function and xmlns required with a SOAP POST.'
        if filename or parameters or body:
            raise TypeError, 'filename, parameters, body not allowed with SOAP.'

        addheaders.append( ('SOAPAction', function) )
        addheaders.append( ('Content-Type', 'text/xml; charset=UTF-8') )
        argtext = ''
        for arg in soapargs:
            argtext += dict2xml(arg)
        argtext = argtext.strip()
        body = soap_envelope % locals()

    elif parameters:                    # posting form data/query
        if filename or body:
            raise TypeError, 'filename, parameters, body not allowed together.'

        addheaders.append( ('Content-Type',
            'application/x-www-form-urlencoded') )
        body = urllib.urlencode(parameters)

    elif filename:                      # posting a file upload
        if parameters or body:
            raise TypeError, 'filename, parameters, body not allowed together.'

        import mimetools, mimetypes                 # build mime headers
        boundstr = mimetools.choose_boundary()
        bname = os.path.basename(filename)
        dataf = file(filename, 'rb')                # throws IOError if issue

        pre  = '--%s\r\n' % boundstr
        pre += 'Content-Disposition: form-data; filename="%s"\r\n' % bname
        pre += 'Content-Transfer-Encoding: binary\r\n'
        pre += 'Content-Type: %s\r\n\r\n' % (
            mimetypes.guess_type(filename)[0] or 'application/octet-stream')
        post = '\r\n--%s--\r\n\r\n' % boundstr
        body = [pre, dataf, post]

        clen = 0                                    # figure out content length
        for item in body:
            if type(item) is file:  clen += os.path.getsize(item.name)
            else:                   clen += len(item)

        addheaders.append( ('Content-Length', str(clen)) )
        addheaders.append( ('Content-Type',
            'multipart/form-data; boundary=%s' % boundstr) )

    # else generic post
    response = _http_call('POST', url, addheaders, authstr, body, debug)
    if locals().get('dataf'): dataf.close()
    return response


def _http_call(verb, url, addheaders=None, authstr='', body='', debug=False):
    'Basic HTTP call to a server.'

    import socket
    if debug and st:                                # redirect stdout
        orig_stdout = sys.stdout
        sys.stdout = st.fileLogger(log, 'debug')
    proto, hoststr, path = handle_url(url)          # parse url
    if addheaders is None: addheaders = []
    if isinstance(body, basestring):
        body = body.encode('utf-8','replace')       # b4 content-length header

    headers = [
        ('Host', hoststr),
        ('User-Agent', usr_agnt),
        ]
    if not 'Content-Length' in [ h[0]  for h in addheaders]:
        headers.append( ('Content-Length', str(len(body))) )
    if authstr:
        headers.append( ('Authorization', 'Basic ' +
            base64.encodestring(authstr).rstrip()) )
    if addheaders:
        headers = headers + addheaders

    # -- Send -------------------------------------------------------
    http_conn = ( httplib.HTTPSConnection(hoststr) if proto.endswith('s') else
                  httplib.HTTPConnection(hoststr) ) # open connection
    if debug:  http_conn.set_debuglevel(1)
    http_conn.putrequest(verb, path)
    if debug:
        print 'Connect-To:', hoststr
        print '-----------------------------'
        print verb, path

    for header in headers:                          # set headers
        http_conn.putheader(*header)
        if debug: print '%s: %s' % (header[0], header[1])

    if debug:
        print
        if type(body) is list:
            bodystr = '{\n'
            for item in body:
                bodystr += str(item)
            print bodystr
        else:  print '{\n%s' % body
        # elif :                   print '{\n%s' % body[:128]
        print '} -----------------------------'

    try:                                            # send headers, body
        http_conn.endheaders()
        if type(body) is list:                      # file upload sends
            for item in body:                       # [str, file, str]
                http_conn.send(item)
        else:
            if verb == 'PUT' and callable(body):
                body(http_conn)                     # chunked encoding
            else:
                http_conn.send(body)                # normal send

        # -- Response ---------------------------------------------------
        # fetch HTTP reply headers and the response
        if debug:  print '\n\n=============================\n'
        resp = http_conn.getresponse()
        body = ''   # reset
        # if not resp.status == 401:  # there is no body with this one
        try:                        body = resp.read()
        except socket.error, e:     log.warn(str(e))
        except httplib.IncompleteRead, e:
            log.warn('%s -- A known bug with CM typically when given an '
                'incorrect password.' % e)
        if debug:  print '---------------------\n'
        ctype = resp.getheader('Content-type')

        http_conn.close()
        if debug and st:  sys.stdout = orig_stdout  # restore
        return resp.status, resp.reason, body, ctype

    except socket.error, e:
        if debug and st:  sys.stdout = orig_stdout  # restore
        raise IOError, str(e)

