'''
    scws.py - (C) 2008-2010 Scala, Mike Miller
    A simple object-oriented interface to Scala Content Manager Web Services.
    Send questions regarding this module to mike dot miller at scala dot com.

    This module allows remote functions to be called without limit from the
    client.  This design results in the elimination of the drudge work commonly
    associated with SOAP, facilitates rapid development, and provides complete
    flexibility over functions and arguments.  However, this also means that
    error checking is only done at the server.

    If client side validation is a requirement, instead use a comprehensive
    WSDL-based python SOAP Library, e.g: ZSI or suds.

    How to use this module:
        import scws
        hoststr = 'services.scala.com:8082'
        baseurl = 'http://%s/ContentManager/' % hoststr
        authstr = 'user:pass'

        # Create a Content Manager object, pass api_vers='v1.1' if necessary
        cm = scws.ConManager(baseurl, authstr)

        players = cm.player.list()  # ContentManager.servicename.funcname()

        # Use dictionaries or "Transfer Objects" to send parameters if desired:
        src = dict(column='revision', restriction='LESS_THAN', value=5)
        src = scws.TObj(column='revision', restriction='LESS_THAN', value=5)

        templates = cm.template.list(searchCriteria=src)  # exec func

        for template in templates:
            print ' *', template.name

    Next, see the tutorial at:
       https://developer.scala.com/dev/index.php/WebServicesTutorial
'''
if True:    # initialize vars and enable folding
    import os
    import logging
    import soaplib
    try:
        import scalalib as sl
    except (ImportError, AttributeError):
        sl = None

    __version__ = '1.25'
    __all__ = ['ConManager', 'TObj', 'soaplib', 'logging']
    _def_api_vers   = 'v1'
    _def_namespace  = 'ns2'
    loggername = 'scalalib.' + __name__
    log = logging.getLogger(loggername)
    if sl and hasattr(sl, '_nullh'):    # if not available or old vers
        log.addHandler(sl._nullh)       # quiet "no handler" error messages


class _CMService:
    '''
        A class representing a Scala Web Service.
        Passes all function calls to the service endpoint of the
        Content Manager, whose name is specified upon construction.
    '''
    def __init__(self, parent, servicename):
        '''
            Arguments:
                parent        - A link back to the parent object.
                servicename   - Accepts the simple lowercase version used in
                                URLs (e.g. "player") as well as the mixed-case
                                version used in the API docs (e.g. "PlayerRS").
        '''
        self.parent = parent
        if servicename.endswith('RS'):      # remove it and lower first capital
            self.service = servicename[0].lower() + servicename[1:-2]
        else:
            self.service = servicename

    def __getattr__(self, attr):
        'Save function name, redirect attribute access to the method "call."'
        self.functionname = attr
        return self.call

    def call(self, *args, **kwargs):
        '''
            Calls the function (named by getattr) of this web service.

            Accepts dictionaries and/or TObjs as arguments or keyword arguments.
            Argument names and/or TObj sub-types can be set or overridden using
            the names given as keywords.
        '''
        import httplib as http              # to use its constants
        arglist = []                        # collect arguments here
        for arg in args:                    # std args
            if isinstance(arg, TObj):       # convert TObj to dictionary first
                arg = arg.__get_dict__(wrap=True)
            arglist.append(arg)
        argcount = len(arglist)             # record pos, for non-TObj below

        for kwname in kwargs:               # collect any keyword args
            kwvals = kwargs[kwname]
            if type(kwvals) != list: kwvals = [kwvals] # if not list create one
            for item in kwvals:
                if isinstance(item, TObj):  # convert to dictionary
                    item = item.__get_dict__()
                elif type(item) is bool:
                    item=str(item).lower()  # Java CM wants bool lowercase
                elif type(item) is dict:
                    for key in item:        # "
                        if type(item[key]) is bool:
                            item[key] = str(item[key]).lower()

                if str(item).isdigit():     # start if again, ints first
                    arglist.insert(argcount, {kwname:item})
                else:
                    arglist.append( {kwname:item} )

        log.info( '%s %s.%s%s' % (self.parent.api_vers, self.service,
            self.functionname, tuple(arglist)) )
        try:        # POST query
            response = soaplib.post(
                self.parent.baseurl + self.service,                 # url
                function='%s:%s' % (self.parent.nspace, self.functionname),#func
                xmlns=self.parent.namespace,                        # xmlns
                soapargs=arglist,                                   # soapargs
                authstr=self.parent.authstr,                        # authstr
                addheaders=[],                                      #prvnt issue
                debug=log.isEnabledFor(logging.DEBUG) ) # Don't create debug txt
                                                        # if it won't be used.
        except IOError, e:
            log.error('%s: %s', e.__class__.__name__, e)
            raise IOError, e
        # print the response, if desired
        log.debug('')
        log.debug('Response: %s\n' % (response,))

        try:   http.OK            # ensure compatibility with py 2.3
        except AttributeError:
            http.OK, http.INTERNAL_SERVER_ERROR, http.NOT_FOUND = 200, 500, 404

        # handle response tuple (status, stat text, body, ctype) and any errors
        status, reason, body, ctype = response
        msgtext = ''
        if status == http.OK:      # 200 OK we in business
            if body and ctype and ctype.startswith('text/xml'):  # pprint
                from xml.dom.minidom import parseString
                log.debug('{\n%s' % parseString(body).toprettyxml(indent='    ') )
            roottag = '{http://%s.api.cm.scala.com}%s%s' % (
                self.parent.api_vers, self.functionname, 'Response') # etree ns
            response_list = soaplib.xml2list(body, roottag)
            # Convert dicts to TObjs for return
            response_list = [ TObj(**adict) for adict in response_list ]
            return response_list

        # continue on only if response is not OK
        elif status == http.INTERNAL_SERVER_ERROR:   # parse CM error msg
            roottag = '{http://schemas.xmlsoap.org/soap/envelope/}Fault' # etree shenanigans
            msg = soaplib.xml2dict(body, roottag)
            if msg and type(msg) == dict:
                if msg.get('detail'):
                    msg = msg.get('detail').get('faultDetail')
                    msgtext = '%s: %s' % (msg.get('errorCode'), \
                        msg.get('errorDescription'))
                if msg.get('faultcode'):
                    msgtext = '%s: %s' % (msg.get('faultcode'), \
                        msg.get('faultstring'))

        elif body and ctype and ctype.startswith('text/html'):
            # scrub markup from error messages in html
            try:                import scalatools as st
            except ImportError: st = None
            if st:  msgtext = st.scrub_html(body)

        # present error response to user
        errstr = 'Server returned: %s %s' % (status, reason)
        errtxt = '\n\n    %s\n' % (msgtext or body)
        log.error(errstr + errtxt)

        # try to map CM exceptions to Python ones
        if msgtext:
            if msgtext.startswith('IllegalArgumentException'):
                if 'is required as argument' in msgtext: raise TypeError, msgtext
                else:  raise ValueError, msgtext
            elif msgtext.startswith('NameAlreadyExists'):
                raise ValueError, msgtext
            elif msgtext.startswith('soap:Client') and 'Message part' in msgtext:
                raise AttributeError, msgtext
            elif msgtext.startswith('soap:Server'):
                raise EnvironmentError, msgtext
            elif status == http.NOT_FOUND:
                raise IOError, errstr
            raise Exception, msgtext
        else:
            raise Exception, errstr


class ConManager:
    '''
        A class used to define a connection to a Scala Content Manager using its
        Web Service API.  Create an instance of this object in order to execute
        remote procedures against it.

        Additionally, there are several higher-level functions to simplify
        common tasks, such as uploading a file, or handling metadata.
    '''
    def __init__(self, baseurl, authstr, api_vers=_def_api_vers,
        nspace=_def_namespace):
        '''
            Arguments:
                baseurl     - An URL describing the base address of the CM,
                              e.g.: 'http://cm.mydom.com:8080/ContentManager/'
                authstr     - A HTTP Basic Authentication string,
                              e.g.: 'username:password'
            Options:
                api_vers    - Specify which CM API version to use.
                nspace      - Change SOAP namespace.
        '''
        if baseurl.endswith('/'):   sep = ''
        else:                       sep = '/'
        self.baseurl_orig = baseurl + sep
        self.baseurl = '%s%sapi/%s/' % (baseurl, sep, api_vers)
        self.authstr = authstr
        self.api_vers = api_vers
        self.nspace = nspace
        self.namespace = (
            'xmlns:%s="http://%s.api.cm.scala.com"' % (nspace, api_vers) )
        self.services = {}
        self.debug = log.isEnabledFor(logging.DEBUG)

    def __getattr__(self, attr):
        # cache service objects
        if attr not in self.services:
            self.services[attr] = _CMService(self, attr)   # create svc handler
        return self.services[attr]

    def get_metaval(self, item, name):
        '''
            Convenience function to search for and return a metadata value.

            Arguments:
                item        - Name/integer id specifying a media/player item.
                name        - Name of the metadata value to search for.
            Returns:
                The value of the metadata item returned from the server,
                None, if the name is not found, or the appropriate Exception.
            Note:
                For player metadata see scalatools.get_metaval(), its use is less
                expensive as it reads from the local disk, not network.

            Example:
                print cm.get_metaval('pow123.png', 'MediaItem.Category')
        '''
        # check arguments
        if not type(name) in (str, unicode):
            raise TypeError, 'name must be string.'
        if name.startswith('MediaItem.'):
            service = self.media
        elif name.startswith('Player.'):
            log.info('use of scalatools.get_metaval() is less expensive for ' +
                'player metadata lookup.')
            service = self.player
        else:
            raise ValueError, 'Metadata type: "%s" unknown.' % name

        if type(item) is int or (type(item) is str and item.isdigit()):  pass
        elif type(item) is str:  # find media id
            src = TObj(column='name', restriction='EQUALS', value=item)
            item = service.list(searchCriteria=src)[0].id
        else:
            raise TypeError, 'item must be a string or integer.'

        # search for metadata id by name
        src = TObj(column='name', restriction='EQUALS', value=name)
        mlist = service.listMeta(searchCriteria=src)

        if mlist:   metadataid = mlist[0].id    # metadata name only
        else:       return None                 # didn't find the metadata name

        # find the value with the matching metadata name id, else None
        if name.startswith('MediaItem.'):   params = dict(mediaId=item)
        elif name.startswith('Player.'):    params = dict(playerId=item)

        values = service.getMetaValues(**params)  # integers get sent first
        value = None
        for metavalue in values:
            if metavalue.metadataId == metadataid:
                value = metavalue.value
                break
        return value

    def set_metaval(self, item, name, value):
        '''
            Convenience function to set a metadata value on an item.

            Arguments:
                item        - Name/integer id specifying a media item or player.
                name        - Name of the metadata value to search for.
                                Name must start with "MediaItem." or "Player.".
                value       - Value to set.
            Returns:
                The value of the metadata item returned from the server,
                None, if the name is not found, or the appropriate Exception.

            Example:
                print cm.set_metaval('pow123.png', 'MediaItem.Category',
                    'Furniture')
        '''
        # check arguments
        if not type(name) in (str, unicode):
            raise TypeError, 'name must be string.'
        if name.startswith('MediaItem.'):   service = self.media
        elif name.startswith('Player.'):    service = self.player
        else:
            raise ValueError, 'Metadata type: "%s" unknown.' % name

        if type(item) in (str, unicode) and not item.isdigit():  # find item id
            src = TObj(column='name', restriction='EQUALS', value=item)
            items = service.list(searchCriteria=src)
            if items:   item = items[0].id
            else:
                log.error('Item "%s" not found.' % item)
                return None
        elif type(item) is int:  pass
        else:
            raise TypeError, 'item must be a string or integer id.'

        # search for metadata id by name
        src = TObj(column='name', restriction='EQUALS', value=name)
        mlist = service.listMeta(searchCriteria=src)
        if mlist:   metadataid = mlist[0].id
        else:
            log.error('Metadata named: "%s" not found.' % name)
            return None

        # find the value with the matching metadata name id, else None
        if name.startswith('MediaItem.'):   params = dict(mediaId=item)
        elif name.startswith('Player.'):    params = dict(playerId=item)

        # search for and delete existing meta value here
        for metavalue in service.getMetaValues(**params):
            if metavalue.metadataId == metadataid:
                service.deleteMetaValue(metaValueId=metavalue.id)
                break

        mvto = TObj(metadataId=metadataid, value=value)
        result = service.addMetaValue(params, value=mvto)
        if result:  return result[0].value
        else:       return None

    def upload_file(self, filenames, network, chunked=True, subfolder='',
        upload_method='PUT', upload_type='auto'):
        '''
            Convenience function to upload files to this Content Manager.

            Argument:
                filenames           - A single or list of filenames to upload.
                network             - The Scala Network to upload to.
            Options:
                subfolder           - Place files in this subfolder.
                upload_method       - Which HTTP method to use to upload.
                                        "PUT"
                                        "POST" - not fully working yet.
                upload_type         - Upload type, e.g. media|maintenance|auto
                chunked             - Enable chunked transfer encoding on larger
                                      files.
            Returns
                mediaIds            - List of MediaItem id numbers of the files.
                                      If not found available, returns the file
                                      upload id instead.
            Example:
                # See the cm_upload.py script for a general solution.
                fileId = cm.upload_file('pow123.png', 'SCALA_CUSTOMER')[0]
        '''
        if type(filenames) is not list: filenames = [filenames]
        fileIds = []
        for filename in filenames:
            if not os.access(filename, os.R_OK):
                errstr = 'File "%s" cannot be accessed.' % filename
                log.error(errstr)
                raise IOError, errstr
            else:
                log.info('filename: "%s"' % filename )
                basename = os.path.basename(filename)
                # decide on a file type
                if upload_type.lower() == 'auto':
                    if os.path.splitext(basename)[1].lower() in ['.bat', '.cmd',
                        '.py', '.vbs', '.exe']:
                                            upload_type = 'MAINTENANCE'
                    else:                   upload_type = 'MEDIA'
                else:  upload_type = upload_type.upper()

                # Request an upload
                # -----------------------------------------------------------
                path = '/content'
                if subfolder: path = '%s/%s' % (path, subfolder)
                robj = TObj(filename=basename,
                    type=upload_type, path=path, size=os.path.getsize(filename))
                try:  # One error here, we should quit
                    uploadTO = self.uploadfile.requestUpload(arg0=robj)[0]
                except Exception, e:
                    log.error(str(e))
                    raise type(e), e

                fileId = uploadTO.mediaItemId or uploadTO.fileId # new attribute
                uploadAs = uploadTO.uploadAsFilename
                log.debug('as id#:%s - %s,' % (fileId, uploadAs))

                # Now, upload file
                # -----------------------------------------------------------
                import httplib as http  # use constants
                if upload_method == 'POST':
                    posturl = self.baseurl_orig + 'servlet/uploadFile'
                    try:
                        response = soaplib.post(posturl, filename=basename,
                            addheaders=[ ('filenameWithPath',
                            '%s%s/%s' % (network, path, uploadAs) ) ],
                            authstr=self.authstr, debug=self.debug)
                    except Exception, e:
                        log.error('%s: %s' % (type(e), e) )
                        raise e

                    if response[0] == http.OK:
                        log.debug('Uploaded.')
                    else:
                        errstr = 'file not uploaded: %s %s' % (
                            response[0], response[1])
                        log.error(errstr)
                        raise Exception, errstr

                elif upload_method.startswith('PUT'):
                    desturl = '%sdata/webdav/%s%s/%s' % (
                        self.baseurl_orig, network, path, uploadAs)
                    try:  # response is a tuple (code, abstract, document)
                        response = soaplib.put(filename, desturl,
                            authstr=self.authstr, chunked=chunked, debug=self.debug)
                    except Exception, e:
                        log.error(str(e))
                        raise e

                    if response[0] == http.CREATED:  # 201
                        try:  # Notify the server that upload is finished
                            self.uploadfile.uploadFinished(arg0=uploadTO.fileId)
                        except Exception, e:
                            log.error(str(e))
                            raise e
                        log.debug('Registered.')
                    else:
                        errstr = 'file not uploaded: %s %s' % (
                            response[0], response[1])
                        log.error(errstr)
                        raise Exception, errstr

                log.info('Done.')
                fileIds.append(fileId)
        return fileIds


class TObj(object):
    '''
        A class representing a generic "Transfer Object" that can be converted
        back and forth to a dictionary or XML representation passed to the
        remote host.
        Note:
            Use of this object is not necessary in parameters of Scala CM
            webservice calls.  It may be easier to use a dict instead.
            However, TObjs will be returned and offer a number of small
            conveniences over dicts.
        Example:
            src = scws.TObj()       # std use
            src.column = 'name'
            src.restriction = 'EQUALS'
            src.value = 'All'

            # shortcut
            src = dict(column='name', restriction='EQUALS', value='All')
    '''
    def __init__(self, *typestr, **kwargs):
        '''
            Constructor Arguments:
                typestr       - An optional argument that can be passed to assign
                                a type string to the object.  This string is
                                ultimately rendered as the tag name (unless
                                overridden at function call time by a keyword).
                                See API docs for Transfer Object definitions.
                kwargs        - Any keyword args passed at construction time are
                                assigned as attibutes of the object.
        '''
        if typestr:  self._typestr = str(typestr[0])
        else:        self._typestr = ''
        for key,val in kwargs.items():
            setattr(self, key, val)
        log.debug('TObj created with: %s' % self.__dict__)

    def __str__(self):
        result = '%s{\n' % (self._typestr or self.__class__)
        items = self.__get_dict__().items();  items.sort()
        for pair in items:
            result += '    %s = "%s"\n' % pair
        result += '}\n'
        return result

    def __repr__(self):
        if self._typestr:   typestr = "'%s', " % self._typestr
        else:               typestr = ''
        return '%s(%s**%s)' % (self.__class__, typestr, self.__get_dict__() )

    def __getattr__(self, attr):  # override to get None instead of attr error
        return self.__dict__.get(attr)

    def __get_dict__(self, wrap=False, includetype=False):
        '''
            Returns a dictionary copy of this object, minus keys starting with
            the underscore character.
            Arguments:
                wrap            - Whether to wrap the dictionary in another
                                  dictionary with the type name as the only key.
                                  This is useful for building the final XML
                                  representation.
                includetype     - Whether to include the type string inside
                                  the dictionary.
        '''
        result = {}
        if includetype and hasattr(self, '_typestr'):
            result['_typestr'] = self._typestr

        for key in dir(self):
            if not key.startswith('_'):
                result[key] = getattr(self, key)

        if wrap and hasattr(self, '_typestr'):  # wrap with name arg, if exists
            result = { self._typestr:result }

        return result

    def __contains__(self, item):
        'Implement "in" tests, e.g.: if "key" in TObj(): pass'
        return item in self.__dict__.keys()

    def __nonzero__(self):
        'Implement truth tests, e.g.: if not TObj(): pass'
        return bool(self.__dict__.keys())

    def __iter__(self):
        return self.__get_dict__(includetype=False).iterkeys()


tobj = TObj     # Make a lowercase name available as well.

