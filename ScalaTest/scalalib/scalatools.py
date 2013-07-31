'''
    scalatools.py - (C) 2007-2012 Scala, Mike Miller, Guillaume Proux, Anthony Prieur
    A toolbox of classes and functions to handle common tasks with Scala.
    Send questions regarding this module to mike dot miller at scala dot com.

    Place in the lib/site-packages folder of your Scala for Python installation.

    Command line usage:
        %prog [options] <function_name> [args]
    Note:
        Args will be converted from strings if True/False/None/Integer, disable
            with a preceding "\\".
    Returns:
        0/1                     - Function return value, strings printed.
        2                       - Command-line error
        3                       - Exception in the function
        4                       - Unknown function
'''
if True:            # initialize, enable folding
    import sys, os, tempfile, logging, urllib2, traceback, time, locale, base64
    from os.path import join
    from glob import glob
    try:                    from win32com.client import Dispatch as COMObject
    except ImportError:     pass
    try:                    import scalalib as sl
    except ImportError:     sl = None

    __version__ = '1.58'
    _wshell  = None
    _wshell_name = 'WScript.Shell'
    _metavals = {}
    _def_blocksize = 8192
    _tempdir = tempfile.gettempdir()
    _def_ini = 'mmos.ini'
    loggername = 'scalalib.tools'
    _log = logging.getLogger(loggername)
    if sl: _log.addHandler(sl._nullh)  # quiet "no handler" error messages


# Classes
# ---------------------------------------------------------------------
class _CSVRecordObj:
    '''
        Allows access to fields of a record (line of csv data) by attributes of
        the object.  Names of attributes are gathered from the fieldnames given
        in the first line of the csv file.
    '''
    def __init__(self, legend, data):
        self.dict = {}
        for i, name in enumerate(legend):
            self.dict[name] = data[i]
    def __getattr__(self, name):
        'Redirect attribute access to our data instead.'
        return self.dict[name]

    # print a string representations of this object
    def __repr__(self):
        return '<%s>' % self.dict.keys()
    def __str__(self):
        return '<%s>' % self.dict.keys()


class fileLogger:
    '''
        A class implementing a file-like interface to the python logging system.
        Useful to redirect debug output that normally would go to stdout/err.

        Writing a line to a fileLogger instance will write it to the given
        logger instead.  Does not flush output until a line ending in '\\n'
        is written, in order to prevent sending space-only log lines.

        Example:
            import sys, scalalib, scalatools
            log = scalalib.get_logger()                       # config logging
            orig_stdout = sys.stdout                          # save for later
            sys.stdout = scalatools.fileLogger(log, 'debug')  # redirect stdout
            # print, print, print
            sys.stdout = orig_stdout                          # restore
    '''
    def __init__(self, logger, level='debug'):
        '''
            Argument:
                logger      - The python logger object to write to.
            Option:
                level       - Emit writes at this logging level.
        '''
        self.logger = logger
        self.level = logging._levelNames[level.upper()]
        self.buffer = ''

    def isatty(self):  return False
    def write(self, text, difflvl=None):
        '''
            Arguments:
                text        - A string to write.
                difflvl     - Specify a non default level for this write.
        '''
        if text.endswith('\n'):             # flush buffer
            text = '%s%s' % (self.buffer, text.rstrip())
            self.logger.log( (difflvl or self.level), text)
            self.buffer = ''                # reset
        else:
            self.buffer += text


class DataChain(object):
    '''
        A class to parse and present XML data, if auto_xml() does not provide
        sufficient flexibility.  Provides a hierarchical object-like interface
        with attributes representing the nodes found.

        Nodes are available as attributes and simulatneously a list of objects
        with the name of the tag + 's', creating a plural tag name.
        XML Attributes are found with '_' + name.

        Arguments:
            document            - One of these types:
                                  string:   A filename for find_file()
                                  file:     An already open xml file
                                  Element:  An ElementTree node
        Option:
            roottag             - Start at the first tag(s) with this name.
                                  Accepts the limited XPath syntax understood
                                  by ElementTree.
        Notes:
            xmlns prefixes are dropped by ElementTree.
            The document is loaded into memory at initialization time, so beware
            with very large files.
            * This new version will return None or an empty sequence on tags
              that don't exist, making it a lot easier to use without try...
              exception blocks.
            * Plural tag attributes are now always created even if only one tag
              exists, for the same reason.

        Example:  # How to use with an RSS feed:
            import scalalib, scalatools as st
            svars = scalalib.sharedvars()
            channel = st.DataChain('rssdoc.xml', roottag='channel')
            svars.desc = channel.description
            svars.image_height = int(channel.image.height)
            svars.titles = [ item.title for item in channel.items ]
            svars.type = channel.items[0].content._type   # xml attributes
    '''
    class _ustr(unicode): # subclass str so we can add attributes
        def __unicode__(self):
            return self

    class _none:
        ''' Note sure why but attributes are call()'ed on this class,
            this is a workaround :/
            This extended None can also be used in a sequence.
        '''
        def __call__(self, *args):
            # print self, 'called with args:', args
            return None
        def __eq__(self, other):
            return isinstance(other, DataChain._none)
        def __repr__(self):
            return '<None %s>' % id(self)
        def __len__(self):
            return 0

    def __init__(self, document, roottag=None):
        try:                    import xml.etree.ElementTree as et  # 2.6
        except ImportError:     import cElementTree as et           # Scala 2.3
        doctype = type(document)

        if et.iselement(document):                  # document is an ElementTree
            self._load(document)
            return
        elif doctype in (str, unicode):  # document is a filename
            document = find_file(document)
        elif doctype is file:  pass
        else:
            raise TypeError, 'unknown type passed as document.'

        root = et.parse(document).getroot()  # et accepts a filename or fileobj
        self.tag = root.tag
        if roottag: self._load(root.find(roottag))
        else:       self._load(root)

    def __str__(self):
        return ('<DataChain ' + str(self.tag) + ':' +
            str(sorted(self.__dict__.keys()) or '') + '>')

    def __repr__(self):
        return '<DataChain Instance>'

    def __nonzero__(self):
        return True

    def __getattr__(self, name):
        'When attrib is not found, return None'
        return DataChain._none()

    def _load(self, parentnode):
        ''' Given an elementtree node, set the attributes of this object with
            the data.
        '''
        for node in parentnode:
            tag = node.tag
            if '}' in tag:  tag = tag.split('}', 1)[1]  # remove {namespace}
            tagpl = tag + 's'

            # add to object
            if len(node):   # has children
                if getattr(self, tag) == DataChain._none():
                   # print 'setting %s with %s' % (tag, DataChain(node))
                   setattr(self, tag, DataChain(node))  # set the first time only

                if getattr(self, tagpl) == DataChain._none():
                    # print 'setting %s with list' % tagpl
                    setattr(self, tagpl, [DataChain(node)] )
                else:
                    # print 'setting %s with list' % tagpl
                    getattr(self, tagpl).append( DataChain(node) )
            else:
                if getattr(self, tag) == DataChain._none():
                    # print 'setting %s with %s' % (tag, DataChain._ustr(node.text))
                    setattr(self, tag, DataChain._ustr(node.text))  # set the first time only

                if getattr(self, tagpl) == DataChain._none():
                    # print 'setting %s with %s' % (tagpl, [DataChain._ustr(node.text)])
                    setattr(self, tagpl, [DataChain._ustr(node.text)] )
                else:
                    # print 'appending %s with %s' % (tagpl, DataChain._ustr(node.text))
                    getattr(self, tagpl).append(DataChain._ustr(node.text))

            # now check for attributes
            attrs = node.attrib.items()
            for attr in attrs:  # singular
                attrname = '_%s' % attr[0]
                setattr(getattr(self, tag), attrname, attr[1])

            for attr in attrs:  # plural
                attrname = '_%s' % attr[0]
                setattr(getattr(self, tagpl)[-1], attrname, attr[1])


# Functions
# ---------------------------------------------------------------------
def auto_csv(filename, filter=None, transforms={}, **sortinfo):
    r'''
        Parses a CSV file and automatically sets the corresponding Scala
            variables with the results.

        Argument:
            filename    - A filename to search for, using find_file().
        Options:
            filter      - An optional function that determines whether a
                          given row will be returned, return True to filter.
            transforms  - An optional mapping of fields to functions.
                          This allows you to transform the data of a field in
                          some way.
            sortinfo    - Optional keyword args containing sorting information.
                          The following arguments are recognized:
                          before:  (bool)  Sort before transforms, def: False
                          reverse: (bool)  Reverse the sort?  def: False
                          fields:  (seq)   Single, or sequence of column numbers
                                           (as int), and/or field-names (as str)
                                           to sort by, in reverse order.
        Results:
            It is easier to use columns rather than rows with Scala, therefore
            shared variables are automatically set with the form:
                csv_columnname = [ row1[i], row2[i], row3[i] ]  # etc
            where columnname is name retrieved from the first row of the file,
            and i is the index of that column.
        Returns:
            Number of records found.
        Note:
            CSV files must have the field names listed in the first line.

        Examples:
            1. The simplest:
                from scalatools import auto_csv
                auto_csv('schedule.csv')

            2. Transform the data before returning:
                auto_csv( 'schedule.csv',
                    transforms={
                        'start_time': st.convert_timestr,     # std function
                        'event_name': lambda x: x.title()} )  # unnamed function

            3. To check if the record is current, use a filter function:
                def check_age(record):      # return True to filter
                    tstr = '%s %s' % (record[0], record[2])
                    return not st.time_in_range(tstr, '%d-%b-%y %H%M', days=3)
                auto_csv('schedule.csv', filter=check_age)

            4. How to do a two column sort of the results (by name or index):
                auto_csv('schedule.csv', before=True, fields=(0,'start_time'),
                    transforms={'start_time': st.convert_timestr} )
    '''
    import csv
    filename = find_file(filename)
    if sortinfo:
        before  = sortinfo.get('before', False)
        reverse = sortinfo.get('reverse', False)
        fields = sortinfo.get('fields', () )
        if type(fields) not in (list, tuple): fields = (fields,)

    # read in data
    _log.debug('parsing "%s"' % filename)
    reader = csv.reader(open(filename))
    legend = reader.next()                          # field names in first line
    data = []
    for i,row in enumerate(reader):
        if row:
            if filter and filter(row): continue   # skip if not current
            data.append(row)                      # skip blanks

    # do any massaging if necessary
    if sortinfo and before:  _auto_sortdata(data, legend, fields, reverse)
    if transforms:
        for row in data:
            for j,name in enumerate(legend):
                if name in transforms:
                    row[j] = transforms[name](row[j])
    if sortinfo and not before:  _auto_sortdata(data, legend, fields, reverse)

    _auto_set([legend] + data, 'csv')
    return len(data)


def _auto_js(filename, filter=None, transforms={}, **sortinfo):
    'The beginnings of an auto json loader.'
    import json
    from collections import defaultdict
    filename = find_file(filename)
    if sortinfo:
        before  = sortinfo.get('before', False)
        reverse = sortinfo.get('reverse', False)
        fields = sortinfo.get('fields', () )
        if type(fields) not in (list, tuple): fields = (fields,)

    def collect(parent, name, value):
        'collect values to data'
        #~ if value != None and value.isspace(): value = ''  # spurious xml text?
        print 'collect:', `parent`, `name`, `value`, 'end'
        varname = parent + name

        numrecs = len( data[parent[:-1]] )
        mycol = data[varname]
        while len(mycol) < numrecs:
            mycol.append('')  # front pad if missing
        mycol.append(unicode(value))

    def iterate(root, parent='', parentobj=None):
        'recurse over nodes'
        print 'iterate:', parent, type(parentobj), type(root)
        if isinstance(root, basestring):    # dict key
            if parentobj:
                collect(parent, root, parentobj[root])
            else:
                print 'no parent:', root
            return

        if type(root) is dict:
            for key in root:
                print '='*70
                newparent = '%s%s_' % (parent, key)
                if type(root[key]) is list or type(root[key]) is dict:
                    iterate(root[key], parent=newparent, parentobj=root)
                collect(parent, key, root[key])
        elif type(root) is list:
            for obj in root:
                newparent = '%s%s_' % (parent, 'list')
                if type(obj) is list or type(obj) is dict:
                    iterate(obj, parent=newparent, parentobj=root)
                else:
                    collect(parent, obj, root[obj])


    # read in data
    _log.debug('parsing "%s"' % filename)
    data = defaultdict(list)                # creates a list by default
    with file(filename) as f:
        response = json.load(f)

    iterate(response)
    #~ return
    print '-' *50
    for obj in data:
        print obj, data[obj]
    print '-' *50
    print type(data), len(data), data.keys()
    print '-' *50


    legend = [ key for key in data if key ]
    longest = sorted([ len(val) for val in data.values() ])[-1]
    newdata = []

    # Convert cols into rows.  Unfortunately need to do this to sort, then back
    # to columns for hand off to Scala in _auto_set.  Should be a better way.
    for rowidx in range(longest):
        record = []
        for col in legend:
            col = data[col]
            while len(col) < longest: col.append('')  # back pad if missing
            record.append(col[rowidx])
        newdata.append(record)
    data = newdata

    _auto_set([legend] + data, 'js')
    return len(data)


def auto_sql(connstr, query, module='adodbapi', connectf='connect', transforms={}):
    '''
        Queries a SQL data source and automatically sets the corresponding Scala
            variables with the results.

        Arguments:
            connstr     - A connection string describing the data source.
            query       - A valid SQL query statement (select/where/order/etc).
        Options:
            module      - The dbi-compatible interface module to use.
            connectf    - A string containing the name of the function to
                          connect with, if not named "connect".
            transforms  - An optional mapping of fields to functions.  This
                          allows you to transform the data of a tag in some way.
        Results:
            Scala variables are automatically set with the form:
                sql_columnname = [ row1[i], row2[i], row3[i] ]  # etc
            where columnname is name of a given field, and i is the index
            of that column.
        Returns:
            Number of records found.
        Notes:
            dbi module must implement cursor.description.
            It is possible to use a connection string to not only query online
            databases, but ODBC DSNs, .mdb/.xls files, and HTML tables as well.
            Search online for "connection strings" for examples.

        Example:
            from scalatools import auto_sql
            auto_sql( connstr, 'select * from table_page',
                transforms={u'item': lambda x: x.upper()} )
    '''
    import dbi
    dbimod = __import__(module)
    if module == 'odbc' and connectf == 'connect': connectf = 'odbc'
    # find the correct function to create the connection object
    conn = getattr(dbimod, connectf)(connstr)

    # query db
    _log.debug('connecting to: %r' % connstr)
    _log.debug('querying: %r' % query)
    cursor = conn.cursor()
    cursor.execute(query)
    legend = tuple([ x[0] for x in cursor.description ]) # lc compat w/2.3
    data = cursor.fetchall()
    datalen = len(data)

    if transforms:
        data = list(data)    # tuples are read-only
        for i,row in enumerate(data):
            for j,name in enumerate(legend):
                if name in transforms:
                    if type(data[i]) is tuple: data[i] = list(row)
                    data[i][j] = transforms[name](row[j])
        data = [legend] + data
    else:
        data = (legend,) + data

    _auto_set(data, 'sql')  # set variables
    return datalen


def auto_xml(filename, roottag='', filter=None, transforms={}, **sortinfo):
    r'''
        Parses an XML file and automatically sets the corresponding Scala
            variables with the results.

        Argument:
            filename    - A filename to search for, using find_file().
        Options:
            roottag     - The top level tags to search for.  Can use the limited
                          XPath syntax used by ElementTree findall() function.
            filter      - An function that determines whether a given record
                          will be returned, return True to remove. (CSV Ex.#3)
            transforms  - A mapping of tags to functions.  This allows
                          you to transform the data of a tag in some way.
            sortinfo    - Optional keyword args containing sorting information.
                          The following arguments are recognized:
                          before:  (bool)  Sort before transforms, def: False
                          reverse: (bool)  Reverse the sort?  def: False
                          fields:  (seq)   Single, or sequence of column numbers
                                           (as int), and/or field-names (as str)
                                           to sort by, in reverse order.
        Results:
            Scala variables are automatically set with the form:
                xml_childtag_grandchildtag = [ first val, second val, ... ]
                xml_childtag__attribute = 'value'  # two underscores before attr
        Returns:
            Number of records found.
        Notes:
            If the same tag repeats in the input data, the Scala variable will
            be assigned as an array of the items found.  Only data in arrays
            can be filtered and sorted.

        Examples:
            1. The simplest:
                from scalatools import auto_xml
                auto_xml('rssdoc.xml', 'channel')

            2. Transform the data before return:
                import scalatools as st
                def strip(value):
                    return value.strip()
                auto_xml('rssdoc.xml', 'channel', transforms={'title':strip})

            3. Using a lambda or type conversion instead:
                auto_xml( 'rssdoc.xml', 'channel',
                    transforms={ 'language': lambda x: x.upper(),
                    'content__height':int } )  # how to alter an attribute
    '''
    try:                    import xml.etree.ElementTree as et  # Py 2.6
    except ImportError:     import cElementTree as et           # Scala Py 2.3
    from collections import defaultdict

    filename = find_file(filename)
    if sortinfo:
        before  = sortinfo.get('before', False)
        reverse = sortinfo.get('reverse', False)
        fields = sortinfo.get('fields', () )
        if type(fields) not in (list, tuple): fields = (fields,)

    _log.debug('parsing "%s"' % filename)
    root = et.parse(filename).getroot()
    if roottag:
        root = root.findall(roottag)
        if len(root) == 0: return           # nothing found
        if len(root) == 1: root = root[0]   # if single root, don't show root tag
    data = defaultdict(list)                # creates a list by default

    def collect(parent, name, value):
        'collect values to data'
        if value != None and value.isspace(): value = ''
        varname = parent + name

        numrecs = len( data[parent[:-1]] )
        mycol = data[varname]
        while len(mycol) < numrecs: mycol.append('')  # front pad if missing
        mycol.append(value)

    def iterate(root, parent=''):
        'recurse over nodes'
        for node in root:
            tag = node.tag
            if '}' in tag:  tag = tag.split('}', 1)[-1]  # remove {namespace}

            # add to object
            if len(node):   # has children
                newparent = '%s%s_' % (parent, tag)
                iterate(node, parent=newparent)
                collect(parent, tag, node.text)
            else:
                collect(parent, tag, node.text)

            # now check for attributes, add with two underscores
            items = node.attrib.items()
            for item in items:
                collect(parent, '%s__%s' % (tag, item[0]), item[1])

    iterate(root)  # read in data

    # get data into shape, first name value pairs
    datamap = dict([ (k, data.pop(k)[0]) for k in data.keys() if len(data[k]) == 1 ])
    legend = [ key for key in data if key ]
    longest = sorted([ len(val) for val in data.values() ])[-1]
    newdata = []

    # Convert cols into rows.  Unfortunately need to do this to sort, then back
    # to columns for hand off to Scala in _auto_set.  Should be a better way.
    for rowidx in range(longest):
        record = []
        for col in legend:
            col = data[col]
            while len(col) < longest: col.append('')  # back pad if missing
            record.append(col[rowidx])
        newdata.append(record)
    data = newdata

    # do any massaging if necessary
    if sortinfo and before:  _auto_sortdata(data, legend, fields, reverse)
    if filter: data = [ row for row in data  if not filter(row) ]
    if transforms:
        for row in data:
            for j,fieldname in enumerate(legend):
                if fieldname in transforms:                 # look for full name
                    row[j] = transforms[fieldname](row[j])
                else:
                    fieldname = fieldname.split('_')[-1]    # look for short
                    if fieldname in transforms:
                        row[j] = transforms[fieldname](row[j])
    if sortinfo and not before:  _auto_sortdata(data, legend, fields, reverse)

    _auto_set(datamap, 'xml')
    _auto_set([legend] + data, 'xml')
    return len(data)


def _auto_set(data, var_prefix):
    'Given a data set, set Scala vars with the contents of data.'
    if type(data) is dict:                  # xml
        legend = data.keys()
        dtype = dict
    elif type(data) in (tuple, list):       # tuple (sql), list (csv)
        legend, data = data[0], data[1:]    # slice from first rec
        dtype = tuple
    def shorten(item, maxlen=8):
        'Shorten lengthy data for display.'
        if type(item) in (str, unicode) and len(item) > maxlen:
            item = item[:maxlen] + '...'
        return item

    # Scala prefers columns rather than rows so we'll set the vars in that order.
    logging_enabled = _log.isEnabledFor(logging.INFO)
    frame = 0
    for i,name in enumerate(legend):
        if dtype is tuple:
            values = []             # values = [ record[i] for record in data ]
            for record in data:     # sometimes records are missing fields
                try:                values.append(record[i])
                except IndexError:  values.append('')
        elif dtype is dict:
            values = data[name]
            if not values or not [ v for v in values if v ]:
                continue    # skip if no val at all is set.
        varname = '%s_%s' % (var_prefix, name)
        varname = varname.replace(' ', '_') # swap spaces for underscores
        shortvals = values
        if logging_enabled:
            if type(values) is list:
                shortvals = [ shorten(x) for x in values ]
            _log.info( '%s to %r (%s)' % (varname, shortvals, len(values)) )
        if type(values) is list and len(values) == 1:   # work around bug, array
            values.append('')                           # of len 1 doesn't show

        found = False
        if frame:                       # short circuit if already found frame
            try:                        # set the Scala vars
                sys._getframe(frame).f_globals[varname].value = values
                found = True
            # except ValueError:  pass   # call stack not that deep
            except KeyError:    pass
        else:
            for j in range(2, 8):           # look for the var in a few frames
                try:                        # set the Scala vars
                    sys._getframe(j).f_globals[varname].value = values
                    frame = j;  found = True
                    break   # on success
                except ValueError:  break   # call stack not that deep
                except KeyError:    pass
        if not found:
            _log.debug('%s.value not found.' % varname )


def _auto_sortdata(data, legend, fields, reverse):
    'Simple data sort for auto* functions.'
    for field in fields:
        if type(field) is str:  field = legend.index(field)
        if type(field) is int and (0 <= field < len(legend)):
            data.sort( lambda x,y: cmp(x[field], y[field]),
                reverse=reverse)


def convert_timestr(timestr='', infmt='%H%M', outfmt='%I:%M %p', lstrip=''):
    '''
        Converts a time string to another format.
        By default converts from 24 hour to 12 hour format, e.g.:
            '1800'  -->  '6:00 PM'

        Options:
            timestr     - The string to format, else uses the current time.
            infmt       - The format of input timestr, if given.
            outfmt      - The format to return.
            lstrip      - Strip this character from the front of the string.
        Returns:
            A time string in the format specified by outfmt.
        Note:
            Python time format specifiers are described here:
            http://docs.python.org/library/time.html#time.strftime
    '''
    if timestr:
        t = time.strptime(timestr, infmt)
        outstr = time.strftime(outfmt, t)
    else:
        outstr = time.strftime(outfmt)
    if lstrip: outstr = outstr.lstrip(lstrip)
    return outstr


def file_is_current(filename, **time_range):
    '''
        Checks whether a file has yet to meet its expiration date.

        Argument/Option:
            filename    - The file to check.
            time_range  - Specify the time range with the same keyword args as a
                          timedelta obj, e.g: (days=2, minutes=30). See Notes.
        Returns:
            If the given file is "up to date" and current, returns True.
            i.e.:   Exists and its modification timestamp is between now and the
                    given time range in the *past*, e.g. the last 15 mins.
            If the file is outdated, returns False.
            If the file does not exist or not found, returns None.
        Notes:
            timedelta docs can be found here:
                http://docs.python.org/library/datetime.html#timedelta-objects
            time_range args are assumed to be negative and are converted if not.
            Uses time_in_range().

        Example:
            from scalatools import file_is_current
            if file_is_current(filename='D:/rssdoc.xml', hours=12):
                pass   # proceed to ...
    '''
    if os.path.exists(filename):
        timestamp = os.stat(filename).st_mtime
        args = {}
        for key in time_range:      # convert positive args to negative
            if time_range[key] > 0:     args[key] = time_range[key] * -1
            else:                       args[key] = time_range[key]
        return time_in_range(timestamp=timestamp, **args)
    else:
        return None


def find_file(filename, tmpfolder=''):
    '''
        Searches for a given filename along the search path specifed below:
            - Given filename in current folder, or as absolute path.
            - Content:  Scala virtual folder.
            - The user's %TEMP% folder

        Argument:
            filename        - The file/path to search for.
                              May be an absolute, relative, or Scala-style path.
        Option:
            tmpfolder       - The complement of grab_url()'s tmpfolder option.
                              When checking in %TEMP%, look in this subfolder.
        Returns:
            The first filename/path verified to exist, as an absolute path.
            If not found, raises IOError.
        Example:
            from scalatools import find_file
            path = find_file('image.png')
    '''
    newpath = filename                          # Make copy
    if not os.path.exists(newpath):             # look in the CWD
        if ':' in newpath and newpath.index(':') != 1:  # Scala-style path
            newpath = sl.lock_content(filename, report_err=False)
        else:
            scpath = join('Content:\\', tmpfolder, filename)
            newpath = sl.lock_content(scpath, False)
        if not newpath: newpath = filename      # COM Error caught, reset

        if not os.path.exists(newpath):         # look in tempfolder
            newpath = join(_tempdir, tmpfolder, filename)
            if not os.path.exists(newpath):
                errstr = '"%s" not found.' % filename
                _log.error(errstr)
                raise IOError, errstr

    newpath = os.path.abspath(newpath)
    _log.debug('"%s" found at: "%s"' % (filename, newpath) )
    return newpath


def get_metaval(name, filename='ScalaNet:\\metadata.xml'):
    '''
        Read Player metadata values.

        Argument:
            name            - The name of the desired value.
        Option:
            filename        - Use a storage file other than the default.
        Returns:
            The metadata value, or None if not found.
        Notes:
            Does not work under Designer, unless an absolute path is passed.
        Example:
            from scalatools import get_metaval
            location = get_metaval('Player.location')
    '''
    if _metavals:  # cached
        value = _metavals.get(name)
    else:
        value = None
        def convert(entry):
            if entry._type == 'integer':
                return int(entry._value)
            elif entry._type == 'boolean':
                return (entry._value.lower() == 'true')
            else: # entry._type == 'string' or *:
                return entry._value
        try:
            filename = find_file(filename)
            scala_md = DataChain(filename)
            if hasattr(scala_md, 'entrys'):
                for entry in scala_md.entrys:
                    _metavals[entry._name] = convert(entry)
                value = _metavals.get(name)
                _log.info('%s = %s' % (name, value) )
            del filename  # explicitly deletes lock, if present and no refs.
        except IOError:
            _log.debug('%s in "%s" not found.' % (name, filename) )
    return value


def _run_under_player():
    winpath = sl.lock_content('ScalaNet:\\metadata.xml', report_err=False)
    if winpath:  return True
    else:        return False


def get_info(hint=None):
    '''
        Read current application installation information from the registry.

        Option:
            hint            - Read from 'player' or 'designer' key, else guess.
        Returns:
            A dictionary with the following keys, or empty if not found.
                ArtPath, EULALanguage, FirewallAllowed, Language
                ProductExecutable, ProductFolder, ProductVersion
                ReleaseName, TransmissionClientService (Player only)
        Example:
            from scalatools import get_info
            version = get_info().get('ProductVersion', '')[2:]
    '''
    data = {}
    if _run_under_player() or hint == 'player':
        regkeys = ['SOFTWARE\\Scala\\InfoChannel Player 5']
    else:
        regkeys = ['SOFTWARE\\Scala\\InfoChannel Designer 5',
            'SOFTWARE\\Scala\\InfoChannel Player 5']
    for regkey in regkeys:
        try:
            import _winreg
            key =_winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, regkey)
            for i in range(_winreg.QueryInfoKey(key)[1]):
                name, val, type = _winreg.EnumValue(key, i)
                data[name] = val
            _winreg.CloseKey(key)
            break
        except:
            _log.error('Registry "HKLM\%s" not found.' % regkey)
    return data


def get_ini(filename=_def_ini, section='scala', hint=None, raiserr=False):
    '''
        Read settings from an ini file.  Defaults to the mmos.ini of the
        current application.

        Options:
            filename        - The name of the file to read from.
            section         - A case-insensitive section name to read from.
            hint            - Read mmos.ini from 'player' or 'designer' folder.
            raiserr         - Whether to raise IOError on failure.
        Returns:
            A dictionary containing any data found under the given section;
            empty on error.
        Example:
            from scalatools import get_ini
            mmosini = get_ini()
    '''
    import ConfigParser
    import codecs
    data = {}
    if filename == _def_ini:
        folder = get_info(hint).get('ProductFolder')
        if folder:
            filename = join(folder, 'mmos.ini')
        _log.debug('filename: "%s"', filename)

    cp = ConfigParser.RawConfigParser()
    try:
        if not os.access(filename, os.R_OK):  raise IOError
        cp.readfp(codecs.open(filename, 'r', 'utf_8_sig')) # skip BOM
        for sect in cp.sections():  # insensitive
            if sect.lower() == section.lower():
                section = sect
        data = dict(cp.items(section))
    except IOError, e:
        if raiserr:  raise e
        else:        _log.error('File "%s" not found.' % filename)
    except ConfigParser.NoSectionError:
        _log.error('Section %s not found.', section)
    return data


def get_regval(keypath):
    r'''
        Retrieve a value from the Windows Registry.

        Argument:
            keypath     - Should be an absolute path, including the hive (long
                            or short format) in UPPERCASE, path, and name.
        Returns:
            The specified value.
            If the key doesn't exist, or other error, returns None.
        Example:
            from scalatools import get_regval
            keypath = r'HKCU\Software\Scala\InfoChannel Designer 5\LogFolderPath'
            value = get_regval(keypath)
    '''
    global _wshell
    value = None
    try:
        if not _wshell: _wshell = COMObject(_wshell_name)
        value = _wshell.RegRead(keypath)
        sl._log_report()
    except Exception, err:
        _log.warning('Key path "%s" not found.' % keypath )
    return value


# ---- grab_url support -----------------------------------------------------
class _HDEHandler(urllib2.HTTPDefaultErrorHandler):
    def http_error_default(self, req, fp, code, msg, headers):
        result = urllib2.HTTPError(
            req.get_full_url(), code, msg, headers, fp)
        result.status = code
        return result

class _SRHandler(urllib2.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):  # Moved Permanently
        result = urllib2.HTTPRedirectHandler.http_error_301(
            self, req, fp, code, msg, headers)
        result.status = code
        _log.error('Server returned code 301.  ' +
            'URL has been moved permanently to a new location.  Update ASAP.')
        return result
    def http_error_302(self, req, fp, code, msg, headers):  # Found
        result = urllib2.HTTPRedirectHandler.http_error_302(
            self, req, fp, code, msg, headers)
        result.status = code  # warning given if
        _log.warn('Server returned code 302.  ' +
            'URL has been moved temporarily to a new location.')
        return result


def _decompress(compdata, dcobj=None, encoding='gzip'):
    '''Decompress block with appropriate object from zlib.  "deflate" has
       several meanings so we pass/return the object so it can be updated in
       case of failure.'''
    import zlib
    if not dcobj:
        if 'gzip' in encoding:
            dcobj = zlib.decompressobj(16+zlib.MAX_WBITS)   # gzip fmt
        elif 'deflate' in encoding:
            dcobj = zlib.decompressobj(15)                  # w/zlib header
        else:
            msg = 'unsupported content encoding: ' + encoding
            _log.error(msg)
            raise RuntimeError, msg
    try:
        return dcobj.decompress(compdata), dcobj
    except zlib.error:
        _log.debug('switching to raw deflate from zlib deflate.')
        dcobj = zlib.decompressobj(-15)                    # Try Raw
        return dcobj.decompress(compdata), dcobj


def _extract_auth(url, handlers, HandlerClass):
    'Extract credentials from the host part of an url.'
    import urlparse
    scheme, netloc, path, params, query, frag = urlparse.urlparse(url) # again:/
    authstr, hoststr = netloc.split('@')
    if ':' in authstr: user, pwd = authstr.split(':')
    else:              user, pwd = authstr, ''
    shorturl = urlparse.urlunparse(
        (scheme, hoststr, path, params, query, frag) )
    passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
    passman.add_password(None, shorturl, user, pwd)
    handlers.append(HandlerClass(passman))
    return hoststr                      # authstr removed


def _get_stream_support(filename):
    'Return whether the volume containing filename supports ADS "streams."'
    result = False
    if sys.platform.startswith('win'):
        try:
            import win32api
            FILE_NAMED_STREAMS = 0x00040000  # couldn't find this anywhere else
            drive, path = os.path.splitdrive(os.path.abspath(filename))
            volname, pathsz, fnamesz, volflags, fstrname = (
                win32api.GetVolumeInformation(drive + '/') )
            result = bool(volflags & FILE_NAMED_STREAMS)
        except ImportError:  pass
    return result
_strm_support = _get_stream_support(_tempdir)


def _write_stream(filename, data, streamname=None):
    '''
        Write data to a file/ADS stream using Win32 API.  Returns True on
        success, None on error.
    '''
    if streamname: filename = '%s:%s' % (filename, streamname)
    import win32file, pywintypes
    try:
        h = win32file.CreateFile( filename,
            win32file.GENERIC_WRITE,
            0,                          # No special sharing
            None,                       # No special security requirements
            win32file.CREATE_ALWAYS,    # attempting to recreate it!
            0,                          # Not creating file, so no attributes
            None )                      # No template file
        win32file.WriteFile(h, data)
        h.Close()
        return True
    except pywintypes.error, e:
        _log.error('%s: %s' % (type(e), e) )


def _read_stream(filename, streamname=None, maxsz=4096):
    '''
        Read a file/ADS up to maxsz bytes using Win32 API.  Returns file data on
        success, None on error.
    '''
    if streamname: filename = '%s:%s' % (filename, streamname)
    import win32file, pywintypes
    try:
        h = win32file.CreateFile( filename,
            win32file.GENERIC_READ,
            win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_READ,
            None,                         # No special security requirements
            win32file.OPEN_EXISTING,      # expect the file to exist.
            0,                            # Not creating, so no attributes
            None )                        # No template file
        errcode, data = win32file.ReadFile(h, maxsz)
        if not errcode:
            return data
    except pywintypes.error, e:
        _log.debug('%s: %s' % (type(e), e) )


_mdf_suffix = '.HTTP_Headers.txt'
def _save_properties(filename, streamname=None, **kwargs):
    'Stream or file backed property store.'
    data = ''
    for kwarg in kwargs:
        value = kwargs[kwarg]
        if value is not None:
            data += '%s:%s\r\n' % (kwarg.replace('_','-'), value)
    if _strm_support:
        _write_stream(filename, data, streamname=streamname)
    else:
        outfile = file(filename + _mdf_suffix, 'wb')
        outfile.write(data)
        outfile.close()


def _get_properties(filename, streamname=None):
    'Stream or file backed property store.'
    data, results = '', {}
    if _strm_support:
        if os.access(filename, os.R_OK):
            data = _read_stream(filename, streamname=streamname)
            data = ( data.split('\r\n') if data else [] )   # could be None
    else:
        filename = filename + _mdf_suffix
        if os.access(filename, os.R_OK):
            infile = file(filename, 'r')
            data = infile.readlines()
            infile.close()

    for line in data:
        if not line or line.isspace(): continue
        try:
            name, value = line.split(':', 1)
            results[name] = value
        except ValueError:  # corrupt line
            _log.debug('line corrupt: %r' % line)
    return results


def _grab_url_report(blocks, blocksize, totalsize, progtext='%s'):
    'Calculate download progress and display for grab_url function below.'
    transferred = blocks * blocksize
    if totalsize > 0:
        pcnt = (transferred * 100.0 / totalsize )
        if pcnt > 100: pcnt = 100
        progress = '%.1f%%' % pcnt
    else:
        progress = locale.format('%d', transferred, True)
    _log.debug(progtext % progress)


class _GrabUrlResult(object):
    'An object to hold metadata of the result of a grab_url run.'
    def __init__(self, was_current, abspath='', status=0):
        self.was_current = was_current
        self.abspath = abspath
        if abspath and os.path.exists(abspath):
            self.size = os.path.getsize(abspath)
        else:
            self.size = 0
        self.status = status

    def __repr__(self):
        return '%s(was_current=%s, abspath=%r)' % (
            self.__class__.__name__, self.was_current, self.abspath)

    def __nonzero__(self):
        'Implement truth-tests and bool().  None converted to False.'
        return bool(self.was_current)

    def __eq__(self, other):
        return other == self.was_current

    def __ne__(self, other):
        return not self.__eq__(other)


def grab_url(url, dest=None, filename=None, inst_content=False, postdata=None,
    username=None, password=None, proxy_url=None, timeout=30, tmpfolder='',
    conditional=True, compression=True, addheaders=None,
    blocksize=_def_blocksize, postenc=True, **time_range):
    '''
        Downloads data from an URL to a local copy.  To conserve resources, this
        function will skip subsequent transfers by default.  Downloads are
        skipped completely until the local file has reached its expiration time.
        After expiration, HTTP URLs are also checked and skipped if the remote
        file has not been modified since grab_url() was last run.

        Argument:
            url <string>              - Item to retrieve.
                                        FTP, HTTP URLs may include credentials.
        Options:
            dest <pathstr>            - Copy to another local destination.
            filename <string>         - Save to this filename,
                                          default: URL filename, if available.
            inst_content <boolean>    - Whether to copy to the Content: folder
            postdata <string|dict>    - Use POST, not GET.  Should be a
                                        query string or dictionary.
                                        Unicode must be char-encoded first.
            postenc <bool>            - form-urlencode a postdata string.
            username, password <str>  - Use HTTP Basic authentication,
                                        or FTP login, if necessary.
            proxy_url <string>        - Proxy url, with Basic authstr, only if
                                        necessary to override system settings.
            timeout <float_secs>      - Seconds to wait on socket connection.
            tmpfolder <string>        - Download to this subfolder in %TEMP%.
                                        Useful if filenames clash.
            conditional               - Skip subsequent downloads if an HTTP
                                        URL has not been modified. (GET only)
            compression <boolean|str> - Enable or specify HTTP compression.
            addheaders <[(k,v)]>      - Add/override HTTP request headers with
                                        a list of key, value tuples.
            blocksize <int>           - Configure download block size.
            time_range <args>         - Expiration time, i.e.:
                                        Local copy must be this old (def: 15 mins)
                                        before attempting download.
                                        See file_is_current() for details.
        Notes:
            FTP/HTTP authentication is not encrypted, equivalent to plain text.
            The file is first downloaded to the user's %TEMP% folder, then
            copied to other locations if requested.  Since find_file()
            will find the file in the temp folder, it is not necessary to
            pass the path afterwards to other scalatools functions.
        Raises:
            May raise urllib2.URLError, urllib2.HTTPError, IOError, or a
            RuntimeError on unexpected problems.
        Returns:
            A result object with the following members:
                was_current
                    The result of file_is_current() e.g. {True|False|None}
                    on the local copy from *before* the download attempt.
                abspath
                    Absolute path to the downloaded local copy in the temp
                    folder.
                status
                    The HTTP status code if applicable, else 0.
            The new result object can still be used in truth tests with one
            exception, "result is None" no longer works.  Use
            "result.was_current is None" instead.
            If no Exception was thrown, you can assume an up-to-date local
            copy is now available.

        Example:
            from scalalib import sharedvars as svars
            from scalatools import auto_xml, grab_url
            filename = 'sci.xml'
            try:
                result = grab_url('http://rss.news.yahoo.com/rss/science',
                                   filename=filename, hours=1, minutes=30)
            except Exception:
                svars.message = 'Download not successful.'
            else:
                auto_xml(filename)
    '''
    if True:  # enable folding, initialize vars
        _log.debug( 'options: ' + repr(locals()) )
        if not type(url) in (str, unicode):
            raise TypeError, 'url must be a string, not %s.' % type(url)
        if not time_range: time_range = dict(minutes=15)
        import urllib, urlparse, shutil, httplib as HTTP
        progtext = '%s'
        download = False
        verbose = False
        destpath = None
        dcobj = None                        # decompressor
        infile, outfile = None, None        # make sure always available
        _strname = 'Download.HTTP.Headers'
        locale.setlocale(locale.LC_ALL, '')

        if not filename:
            filename = os.path.basename(urlparse.urlparse(url).path)
            if not filename:
                errstr = 'filename parameter required if url has no filename.'
                _log.error(errstr)
                raise ValueError, errstr
        # define tempfile
        if tmpfolder:
            subpath = join(_tempdir, tmpfolder)
            if not os.path.exists(subpath):
                _log.info('creating: %s' % subpath)
                os.makedirs(subpath)
        tempfname = join(_tempdir, tmpfolder, os.path.basename(filename))

        def copy_if_missing():
            destpath = join(dest, os.path.basename(tempfname))
            if not os.path.exists(destpath):
                _log.warn('%s missing, copying from %%TEMP%%.' % destpath)
                shutil.copy(tempfname, destpath)  # overwrites

    # determine what to do
    current = _GrabUrlResult( file_is_current(tempfname, **time_range),
        abspath=tempfname)
    if current == True: # unfortunately have to do this again to return age:
        age_minutes = (time.time() - os.stat(tempfname).st_mtime) / 60
        _log.info('Retrieved %i minute(s) ago.  Not downloading.' % age_minutes)
    elif current == False:
        progtext = 'File Outdated.  Attempting download ... \n>  %s'
    elif current == None:
        progtext = 'File does not exist.  Attempting download ... \n>  %s'

    if current:
        if dest:
            copy_if_missing()
    else:
        try:
            if os.access(url, os.R_OK):  # url is actually a local file
                if dest:    shutil.copy(url, dest)
                else:       shutil.copy(url, tempfname)
                _log.info('Copied to "%s".' % (dest or tempfname) )
            else:
                # prepare to download file to file.new
                newfname = tempfname + '.new'  # first, remove old .new
                if os.access(newfname, os.W_OK):  os.unlink(newfname)

                # prepare handlers
                handlers = [_HDEHandler()]
                scheme, netloc, path, params, query, frag = (
                    urlparse.urlparse(url) )
                # handle non-standard http urls with embedded authstr info:
                if scheme.startswith('http') and '@' in netloc:
                    netloc = _extract_auth(url, handlers, urllib2.HTTPBasicAuthHandler)

                if username:                            # handle kw args authstr
                    if scheme.startswith('http'):
                        passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
                        passman.add_password(None, url, username, (password or '') )
                        auth_handler = urllib2.HTTPBasicAuthHandler(passman)
                        handlers.append(auth_handler)
                        if len(handlers) > 2:
                            _log.warn('HTTP Authentication entered twice.')

                    elif scheme.startswith('ftp'):            # add authstr to ftp url
                        if '@' in netloc:
                            _log.warn('FTP Authentication entered twice.')
                        authstr = username
                        if password: authstr = '%s:%s' % (authstr, password)
                        netloc = '%s@%s' % (authstr, netloc)

                if proxy_url:
                    parsed = list( urlparse.urlparse(proxy_url) )
                    if parsed[0] == 'http' and '@' in parsed[1]:
                        parsed[1] = _extract_auth(proxy_url, handlers,
                            urllib2.ProxyBasicAuthHandler)
                        proxy_url = urlparse.urlunparse(parsed)
                    proxy_support = urllib2.ProxyHandler( {
                        'http':proxy_url, 'ftp':proxy_url,
                        'https':proxy_url, 'ftps':proxy_url} )  # scheme on ftp?
                    handlers.append(proxy_support)

                if _log.isEnabledFor(logging.DEBUG) and scheme.startswith('http'):
                    try:
                        handlers += [ urllib2.HTTPHandler(debuglevel=1),
                            urllib2.HTTPSHandler(debuglevel=1) ]
                    except TypeError:  pass # python 2.4+ only

                # install handlers
                _log.debug('handlers installed: %s' % handlers)
                opener = urllib2.build_opener(*handlers)
                #~ urllib2.install_opener(opener)  # using directly now

                # quote values, if needed
                if postdata:
                    if type(postdata) is dict:
                        postdata = urllib.urlencode(postdata)
                    elif postenc:
                        postdata = urllib.quote_plus(postdata)
                path = urllib.quote(path)
                query = urllib.quote_plus(query, safe=':&=')

                # reconstitute url, and create request object
                url = urlparse.urlunparse(
                    (scheme, netloc, path, params, query, frag) )
                request = urllib2.Request(url)
                if scheme.startswith('http') and username and password:
                    # auth handler no longer works :/
                    request.add_header('Authorization', 'Basic ' +
                        base64.encodestring('%s:%s' % (username, password)
                        ).rstrip() )
                if compression:
                    request.add_header('Accept-Encoding',
                        (compression if type(compression) is str
                        else 'deflate, gzip') )
                if conditional and not postdata:
                    _log.debug('filesystem supports streams: %s.' % _strm_support )
                    props = _get_properties(tempfname, _strname)
                    for key in props:
                        _log.debug('adding header from property store:  '+ key +
                            ': '+ props[key])
                        request.add_header(key, props[key].rstrip())
                if addheaders:
                    for pair in addheaders:
                        request.add_header(pair[0], pair[1])

                # read url and write to disk
                infile = opener.open(request, postdata, timeout)
                if not url == infile.url:
                    _log.warn('Redirected to: "%s"' % infile.url)
                if hasattr(infile, 'status'):
                    current.status = infile.status
                else:
                    infile.status = HTTP.OK
                if infile.status == HTTP.OK:
                    outfile = file(newfname, 'wb')
                    contenc = infile.headers.dict.get('content-encoding')
                    totalsize = int(infile.headers.dict.get('content-length', 0))
                    blocks = 0
                    while True:  # read and report progress
                        buffer = infile.read(blocksize)
                        if totalsize:  # if no content-length, no report
                            _grab_url_report(blocks, blocksize, totalsize, progtext)
                        if len(buffer) == 0: break
                        if contenc:
                            buffer, dcobj = _decompress(buffer, dcobj, contenc)
                        outfile.write(buffer)
                        blocks = blocks + 1
                    infile.close()
                    outfile.close()

                    # save properties
                    if conditional and not postdata:
                        _save_properties(newfname, _strname,
                            If_Modified_Since = infile.headers.dict.get('last-modified'),
                            If_None_Match = infile.headers.dict.get('etag') )

                    # got new, now remove old
                    if os.access(tempfname, os.W_OK): os.unlink(tempfname)
                    os.rename(newfname, tempfname) # mv new to curr, asap
                    if conditional and not _strm_support:
                        newattrfn, attrfn = (newfname + _mdf_suffix,
                            tempfname + _mdf_suffix)
                        if os.access(attrfn, os.W_OK): os.unlink(attrfn)
                        if os.access(newattrfn, os.W_OK):
                            os.rename(newattrfn, attrfn)
                    if inst_content and sl:   # install (copy) file if necessary
                        sl.install_content(tempfname, subfolder=tmpfolder)
                    if dest:  # copy to new destination
                        destpath = join(dest,os.path.basename(tempfname))
                        shutil.copy(tempfname, destpath)  # overwrites
                    _log.info('Retrieved to "%s".' % (destpath or tempfname) )

                elif infile.status == HTTP.NOT_MODIFIED:
                    _log.info('Filename at HTTP URL has not been modified ' +
                        'since last time, skipping download.')
                    if dest:
                        copy_if_missing()
                    current.was_current = True  # It is up to date, actually.
                else:
                    _log.error('Unable to handle HTTP Response: %s %s, %s\n%s',
                        infile.status, HTTP.responses.get(infile.status,'-'),
                        infile.headers.dict, infile.read())

        except (urllib2.URLError, urllib2.HTTPError), e:
            _log.error('%s: %s' % (type(e), e) )
            raise
        except Exception, e:  # verbose logging for unexpected crashes.
            _log.critical('%s:\n  %s' % (type(e), traceback.format_exc()) )
            rte = RuntimeError('%s: %s'  % (e.__class__.__name__, e))
            rte.logged = True
            for fobj in (infile, outfile):
                if fobj:
                    _log.debug('closing open file: %s' % (
                        fobj.name if hasattr(fobj, 'name') else '<url>') )
                    fobj.close()
            raise rte
    return current
# ---- finish grab_url support ---------------------------------------------


def hide_pointer():
    '''Hide the mouse pointer, e.g. when running a web browser full screen.'''
    import win32api
    from ctypes import windll
    SM_CXVIRTUALSCREEN=78
    SM_CYVIRTUALSCREEN=79
    xpos = windll.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) - 100 # avoid Win
    ypos = windll.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) + 10  # 7 corners
    _log.info('moving cursor to: %s, %s' % (xpos, ypos) )
    win32api.SetCursorPos((xpos, ypos))


def msgbox(msg, title='Scala:Python', icon='info', buttons='ok', def_but='left',
    timeout=10):
    '''
        Display a little message box, sometimes helpful for debugging.

        Argument:
            msg             - A string to display.
        Options:
            title           - Sets the title bar text.
            icon            - One of the following types:
                                'stop', 'question', 'exclamation', 'info',
                                'information'
            buttons         - One of the following button types:
                                'ok', 'ok_cancel, 'abort_retry_ignore',
                                'yes_no_cancel', 'yes_no', 'retry_cancel'
            def_but         - Which button is default: 'left', 'middle','right'.
            timeout         - Close dialog and continue after <timeout> seconds.
        Returns:
            The return value denotes the name of the button that the user
            clicked. If the user does not click a button before timeout seconds,
            'Timeout' is returned.
        Example:
            from scalatools import msgbox
            msgbox('Gort: Klaatu Barada Nikto')
    '''
    buttontype = { 'ok':0, 'ok_cancel':1, 'abort_retry_ignore':2,
        'yes_no_cancel':3, 'yes_no':4, 'retry_cancel':5 }
    default_buttons = { 'left':0, 'middle':256,'right':512 }
    icontype = { 'stop':16, 'question':32, 'exclamation':48, 'info':64,
        'information':64 }
    return_val = { -1:'Timeout', 1:'OK', 2:'Cancel', 3:'Abort', 4:'Retry',
        5:'Ignore', 6:'Yes', 7:'No' }

    # transform strings to id numbers
    buttons = buttontype.get(buttons, 0)
    def_but = default_buttons.get(def_but, 0)
    icon = icontype.get(icon, 64)

    # Raise a message box:
    global _wshell
    try:
        if not _wshell:  _wshell = COMObject(_wshell_name)
        status_code = _wshell.Popup('  %s  ' % msg, timeout, title,
            (icon + buttons + def_but))
        return return_val[status_code]  # and back
    except Exception, err:
        sl._log_report(err)
        raise sl._ObjectNotAvailable, 'Windows Scripting Host: %s' % _wshell_name


def pip(command, args, source=True):
    '''
        Use pip, the Python Package installer; installing pip if necessary.

        Arguments:
            command         One of the pip commands, e.g. 'install'.
            args            A string or list of strings, of packages
                            to install.
            source          Install from source.  Set to False to install a
                            binary egg via easy_install instead.
        Documentation:
            http://www.pip-installer.org/
        Note:
            An argument of args may also be a url to a package archive or
            version control repository, e.g.:
                https://bitbucket.org/birkenfeld/sphinx/get/default.zip
                # source must also be False below:
                http://pypi.python.org/packages/2.6/l/lxml/lxml-2.2.2-py2.6-win32.egg
        Example:
            try:
                import twitter
            except ImportError:
                from scalatools import pip
                pip('install', 'twitter')
                import twitter
    '''
    from subprocess import call
    if type(args) is str:
        args = args.split()
    elif type(args) is tuple:
        args = list(args)
    if source:
        args.insert(0, command)
    scriptsdir = join(sys.exec_prefix, 'scripts')
    if not os.path.exists(scriptsdir):
        scriptsdir = join(sys.exec_prefix, 'bin')

    try:
        import pip
    except ImportError:
        if sys.platform.startswith('win'):
            try:
                import setuptools
            except ImportError:
                # install distribute
                _log.warn('installing distribute ...')
                stat = grab_url('http://python-distribute.org/distribute_setup.py')
                call(stat.abspath, shell=True, cwd=_tempdir)

            # install pip
            _log.warn('installing pip ...')
            cmd = '"%s" pip' % join(scriptsdir, 'easy_install.exe')
            call(cmd)

            # clean up
            [ os.unlink(fn)  for fn in (
                glob(join(_tempdir, 'distribute-*.tar.gz')) +
                glob(stat.abspath)
            )]

        else:
            _log.critical('Install pip with the package manager of your system.')
            return

    args = ' '.join(args)
    _log.info('running pip %s' % args)
    #~ pip.main(args)  # Scala barfs on this :/
    if source:  binary = 'pip.exe'
    else:       binary = 'easy_install.exe'
    cmd = ('"%s" ' % join(scriptsdir, binary)) + args
    _log.debug('command line: %r' % cmd)
    call(cmd)


def purge_cache(folder=None, subdir=None, test=True, ftypes='*.jpg *.xml *.txt',
    **time_range):
    '''
        Deletes specified filetypes from a cache/temp folder, after a given
        expiration date.

        Argument:
            time_range      - Files must be this old before attempting deletion.
                              See file_is_current() for timedelta args.
        Options:
            folder          - The folder to purge, otherwise user's %TEMP%.
            subdir          - Use a subfolder of the main folder above.
            test            - When True, log potential actions but don't delete.
            ftypes          - A file/path search pattern for glob.  Accepts
                                multiple expansions like a command line.
        Returns:
            The number of files it deleted, or would have deleted.
        Example:
            from scalatools import purge_cache
            purge_cache(subdir='newsfeed', ftypes='*.xml', test=False, days=15)
    '''
    if not time_range:  raise TypeError, 'time_range required.'
    folder = folder or _tempdir
    ftypes = (ftypes or '*').split()
    if subdir:  folder = join(folder, subdir)
    filelist = []
    delcount = 0
    for ftype in ftypes:
        pattern = join(folder, ftype)
        filelist.extend( glob(pattern) )

    if os.access(folder, os.W_OK):
        for filename in filelist:
            if os.path.isdir(filename): continue
            if file_is_current(filename, **time_range):
                _log.debug('not deleting "%s"' % filename)
            else:
                if os.access(filename, os.W_OK):
                    delcount += 1  # here so we can get a number during testing
                    if test:
                        _log.info('would delete "%s"' % filename)
                    else:
                        _log.info('deleting "%s"' % filename)
                        try:  os.unlink(filename)
                        except WindowsError, we:
                            _log.error(str(we))
                else:
                    _log.error('Access denied at "%s"' % filename)
    else:
        _log.error('No write access to folder: "%s"' % folder)

    _log.debug('%s file(s) to delete/deleted.' % delcount)
    return delcount


def send_key(key):
    '''
        Sends a key press event to the currently focused application.

        Argument:
            key             - Should be a single-character string representing
                              the key, or a virtual key name, e.g.:
                                'a', 'F12', 'HOME', 'END'.
        Note:
            Unfortunately, this function is not able to send a shifted key.
        Returns:
            True, if successful.
            False, if error.
    '''
    if type(key) not in (str, unicode):
        raise TypeError, 'Key must be a string, representing a single key.'

    if True:  # fold init code
        import string
        from ctypes import windll, POINTER, Structure, Union, pointer, sizeof, \
            c_ulong, c_ushort, c_short, c_long

        # Describe the dll interface, boilerplate code
        PUL = POINTER(c_ulong)
        class KeyBdInput(Structure):
            _fields_ = [('wVk', c_ushort),
                        ('wScan', c_ushort),
                        ('dwFlags', c_ulong),
                        ('time', c_ulong),
                        ('dwExtraInfo', PUL)]

        class HardwareInput(Structure):
            _fields_ = [('uMsg', c_ulong),
                        ('wParamL', c_short),
                        ('wParamH', c_ushort)]

        class MouseInput(Structure):
            _fields_ = [('dx', c_long),
                        ('dy', c_long),
                        ('mouseData', c_ulong),
                        ('dwFlags', c_ulong),
                        ('time',c_ulong),
                        ('dwExtraInfo', PUL)]

        class Input_I(Union):
            _fields_ = [('ki', KeyBdInput),
                         ('mi', MouseInput),
                         ('hi', HardwareInput)]

        class Input(Structure):
            _fields_ = [('type', c_ulong),
                        ('ii', Input_I)]

         # * Virtual Keys, Standard Set
        vkdb = {
            'LBUTTON'  : 0x01,
            'RBUTTON'  : 0x02,
            'CANCEL': 0x03,
            'MBUTTON'  : 0x04,
            'BACK'  : 0x08,
            'TAB': 0x09,
            'CLEAR' : 0x0C,
            'RETURN': 0x0D,
            'SHIFT' : 0x10,
            'CONTROL'  : 0x11,
            'MENU'  : 0x12,
            'PAUSE' : 0x13,
            'CAPITAL'  : 0x14,
            'ESCAPE': 0x1B, 'ESC': 0x1B,
            'SPACE' : 0x20,
            'PRIOR' : 0x21,
            'NEXT'  : 0x22,
            'END': 0x23,
            'HOME'  : 0x24,
            'LEFT'  : 0x25,
            'UP' : 0x26,
            'RIGHT' : 0x27,
            'DOWN'  : 0x28,
            'SELECT': 0x29,
            'PRINT' : 0x2A,
            'EXECUTE'  : 0x2B,
            'SNAPSHOT' : 0x2C,
            'INSERT': 0x2D,
            'DELETE': 0x2E,
            'HELP'  : 0x2F,
            # /* VK_0 thru VK_9 are the same as ASCII '0' thru '9' (0x30 - 0x39) */
            # /* VK_A thru VK_Z are the same as ASCII 'A' thru 'Z' (0x41 - 0x5A) */
            'LWIN': 0x5B,
            'RWIN': 0x5C,
            'APPS': 0x5D,
            'NUMPAD0': 0x60,
            'NUMPAD1': 0x61,
            'NUMPAD2': 0x62,
            'NUMPAD3': 0x63,
            'NUMPAD4': 0x64,
            'NUMPAD5': 0x65,
            'NUMPAD6': 0x66,
            'NUMPAD7': 0x67,
            'NUMPAD8': 0x68,
            'NUMPAD9': 0x69,
            'MULTIPLY'  : 0x6A,
            'ADD' : 0x6B,
            'SEPARATOR' : 0x6C,
            'SUBTRACT'  : 0x6D,
            'DECIMAL': 0x6E,
            'DIVIDE' : 0x6F,
            'F1'  : 0x70,
            'F2'  : 0x71,
            'F3'  : 0x72,
            'F4'  : 0x73,
            'F5'  : 0x74,
            'F6'  : 0x75,
            'F7'  : 0x76,
            'F8'  : 0x77,
            'F9'  : 0x78,
            'F10' : 0x79,
            'F11' : 0x7A,
            'F12' : 0x7B,
            'F13' : 0x7C,
            'F14' : 0x7D,
            'F15' : 0x7E,
            'F16' : 0x7F,
            'F17' : 0x80,
            'F18' : 0x81,
            'F19' : 0x82,
            'F20' : 0x83,
            'F21' : 0x84,
            'F22' : 0x85,
            'F23' : 0x86,
            'F24' : 0x87,
            'NUMLOCK': 0x90,
            'SCROLL' : 0x91,
             # /*
             # * VK_L* & VK_R* - left and right Alt, Ctrl and Shift virtual keys.
             # * Used only as parameters to GetAsyncKeyState() and GetKeyState().
             # * No other API will distinguish left and right keys in this way.
             # */
            'LSHIFT': 0xA0,
            'RSHIFT': 0xA1,
            'LCONTROL' : 0xA2,
            'RCONTROL' : 0xA3,
            'LMENU' : 0xA4,
            'RMENU' : 0xA5 ,
            #if(WINVER >: 0x0400)
            # :  VK_PROCESSKEY'  0xE5
            #endif /* WINVER >: 0x0400 */
            'ATTN'  : 0xF6,
            'CRSEL' : 0xF7,
            'EXSEL' : 0xF8,
            'EREOF' : 0xF9,
            'PLAY'  : 0xFA,
            'ZOOM'  : 0xFB,
            'NONAME': 0xFC,
            'PA1': 0xFD,
            'OEM_CLEAR': 0xFE
            }

        def create_event(vk, wscan):
            FInputs = Input * 1
            extrainfo = pointer(c_ulong(0))
            ii = Input_I()
            ii.ki = KeyBdInput( vk, wscan, 0, 0, extrainfo )
            return FInputs( ( 1, ii ) )  # tuple of (numinputs, input)

    # send the key
    key = key.upper()                   # keydb is in uppercase
    virtualkey = vkdb.get(key, None)    # look for virtual key

    if not virtualkey:                  # maybe it is a standard key
        if key in string.digits or key in string.ascii_uppercase:
            virtualkey = ord(key)       # 0..9, A..Z are same as ascii codes

    if virtualkey:                      # found it, send key
        evt = create_event(virtualkey, 0)
        pntr = pointer(evt)
        sizeofevt = sizeof(evt[0])
        _log.info(key)
        return bool( windll.user32.SendInput(1, pntr, sizeofevt))
    else:
        _log.error('could not find: %s' % key)
        return False


def send_email(body, subject, sent_from, send_to, bodyenc='utf-8', files=(),
    host='localhost', port=25, user='', pwd=''):
    '''
        Sends email.

        Arguments
            body, subject,
            sent_from, send_to  - Required message fields, send_to may be list.
        Options:
            bodyenc             - Specify the text encoding of the body
                                  (default: utf8 + base64)
            files               - Single or list of filenames, or document
                                  tuples (fname, body, mimetype, encoding) to
                                  attach to message.
            host, port          - SMTP Server address and port
            user, pwd           - User and password, if server requires
                                  authentication.
        Note:
            When debug-level logging is enabled, this function will print
            SMTP protocol traffic, *including* file attachments.
        Example:
            from scalatools import send_email
            # how to attach in-memory document:
            textdoc = ('h.htm', '<b>:-)</b>', 'text/html', 'utf-8')
            send_email('Body Text', 'Fascinating Subject', 'sender@domain.com',
                'recipient@domain.com', host='smtp.domain.com', port=2025,
                files=['C:/temp/foo.zip', textdoc] )
    '''
    import smtplib, mimetypes
    from email.MIMEMultipart import MIMEMultipart
    from email.MIMEText import MIMEText
    from email.MIMEBase import MIMEBase
    from email import Encoders
    import email.Utils as ut

    # check arguments
    if isinstance(port, basestring):
        port = int(port)
    if files and type(files) not in (tuple, list):
        files = (files,)
    try:
        _log.info('Sending mail to "%s" using %s:%s.' % (send_to, host, port))
        if files:
            msg = MIMEMultipart()
            msg.preamble = 'This is a multi-part message in MIME format.\n\n'
            msg.attach(MIMEText(body, 'plain', bodyenc))
        else:
            msg = MIMEText(body, 'plain', bodyenc)
        msg['Subject'] = subject
        msg['From'] = sent_from
        if isinstance(send_to, basestring):
            send_to = [send_to]
        msg['To'] = ', '.join(send_to)
        msg['Date'] = ut.formatdate(localtime=True)

        for attachment in files:
            need2read = True
            msgfname = ''
            if type(attachment) is tuple:
                if len(attachment) == 4:        # handle in-memory attachment
                    msgfname, payload, mtype, enc = attachment
                    need2read = False
                elif len(attachment) == 2:      # renamed file
                    attachment, msgfname = attachment
                else:
                    _log.error('incorrect number of args for %r' % (attachment,))
                    break

            if need2read:
                mtype, enc = mimetypes.guess_type(attachment, False)
                with file(attachment,'rb') as f:
                    payload = f.read()
                if not msgfname:
                    msgfname = os.path.basename(attachment)

            if mtype and mtype.lower().startswith('text/'):
                part = MIMEText(payload, mtype.split('/',1)[1], enc)
            else:
                if mtype:   part = MIMEBase( *mtype.split('/', 1) )
                else:       part = MIMEBase('application', 'octet-stream')
                part.set_payload(payload)
                Encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment',
                filename=msgfname)
            msg.attach(part)

        session = smtplib.SMTP(host, port)
        session.set_debuglevel( _log.isEnabledFor(logging.DEBUG) )
        if user: session.login(user, pwd)
        smtpresult = session.sendmail(sent_from, send_to, msg.as_string())
        session.quit()

        if smtpresult:
            for key in smtpresult.keys():
                _log.debug('%s: %s' % (key, smtpresult[key])) # [0]
    except Exception, e:
        _log.debug(traceback.format_exc())
        _log.error('%s: %s' % (e.__class__.__name__, e))
        raise


def set_volume(percent=20, component='main', mute=None):
    '''
        Adjusts the volume settings on the Windows mixer.

        Options:
            percent         - Set the volume to this level, type int(0..100).
            component       - Which to configure: 'main', 'mic', or 'line'
            mute            - True, False, None(use to set volume)
        Returns:
            Mixer command result code.
        Note:
            When mute is toggled, percent is ignored.
            This method is not supported past Windows XP.
    '''
    from ctypes import Structure, POINTER, windll, byref, memset, sizeof,pointer
    from ctypes.wintypes import c_void_p, c_uint, c_char, c_long, DWORD, WORD

    # Tons of declarations
    MIXER_SHORT_NAME_CHARS = 16
    MIXER_NAME_CHARS = 64
    MAXPNAMELEN = 32
    HMIXER = c_void_p
    MIXERLINE_COMPONENTTYPE_DST_SPEAKERS = 4
    MIXERLINE_COMPONENTTYPE_SRC_MIC = 4099
    MIXERLINE_COMPONENTTYPE_SRC_LINE = 4098
    MIXER_GETLINEINFOF_COMPONENTTYPE = 3
    MIXERCONTROL_CONTROLTYPE_VOLUME = 0x50030001
    MIXER_GETLINECONTROLSF_ONEBYTYPE = 2
    MIXER_SETCONTROLDETAILSF_VALUE = 0
    MIXERCONTROL_CONTROLTYPE_MUTE = 0x20010002

    class TARGET(Structure):
        _fields_ = (    ( 'type', DWORD),
                        ( 'deviceid', DWORD),
                        ( 'Mid', WORD),
                        ( 'Pid', WORD),
                        ('driverversion', c_uint),
                        ('pname', c_char * MAXPNAMELEN) )

    class MIXERLINE(Structure):
        _fields_ = (    ( 'size', c_long),
                        ('dst', c_long),
                        ('src', c_long),
                        ('lineid', c_long),
                        ('line', c_long),
                        ('user', c_long),
                        ('component_type', c_long),
                        ('channels', c_long),
                        ('connections', c_long),
                        ('controls', c_long),
                        ('shortname', c_char * MIXER_SHORT_NAME_CHARS),
                        ('name', c_char * MIXER_NAME_CHARS ),
                        ('target', TARGET) )

    class MIXERCONTROL(Structure):
        _fields_ = (    ('size', c_long),
                        ('id', c_long),
                        ('type', c_long),
                        ('count', c_long),
                        ('multipleitems', c_long),
                        ('shortname', c_char * MIXER_SHORT_NAME_CHARS),
                        ('name', c_char * MIXER_NAME_CHARS ),
                        ('min ', DWORD),
                        ('max', DWORD ),
                        ('reserved', DWORD * 11 ) )

    class  MIXERLINECONTROLS(Structure):
        _fields_ = (    ('size', DWORD),
                        ('lineid', DWORD),
                        ('type', DWORD),
                        ('count', DWORD),
                        ('sizecontrol', DWORD),
                        ('pctrl', POINTER(MIXERCONTROL)) )

    class MIXERCONTROLDETAILS(Structure):
            _fields_ = (    ('size', DWORD),
                            ('controlid', DWORD),
                            ('channels', DWORD),
                            ('item', DWORD),
                            ('detailsize', DWORD),
                            ('pdetail', POINTER(DWORD)) )

    # Handle arguments
    if   component == 'main':   component = MIXERLINE_COMPONENTTYPE_DST_SPEAKERS
    elif component == 'mic':    component = MIXERLINE_COMPONENTTYPE_SRC_MIC
    else:                       component = MIXERLINE_COMPONENTTYPE_SRC_LINE

    if mute is None:            controltype = MIXERCONTROL_CONTROLTYPE_VOLUME
    else:                       controltype = MIXERCONTROL_CONTROLTYPE_MUTE
    if percent is None: percent = 0
    elif   percent < 0: percent = 0
    elif percent > 100: percent = 100
    volume = 65535 * percent / 100
    controlvalue = {True: 1, False: 0, None: volume}[mute]

    # save for posterity
    _log.info( 'options: %s' % ( str((percent, component, mute))) )

    handle = HMIXER()
    result = windll.winmm.mixerOpen(byref(handle),0,0,0,0)
    ml = MIXERLINE()
    memset(byref(ml),0,sizeof(ml))
    ml.size = sizeof(ml)
    ml.component_type = component
    result = windll.winmm.mixerGetLineInfoA(handle, byref(ml),
        MIXER_GETLINEINFOF_COMPONENTTYPE)
    if result:  return result

    mlc = MIXERLINECONTROLS();
    mc = MIXERCONTROL()
    memset(byref(mc),0, sizeof(mc))
    memset(byref(mlc),0, sizeof(mlc))
    mlc.size = sizeof(mlc)
    mlc.lineid = ml.lineid
    mlc.type = controltype
    mlc.count = 1;
    mlc.pctrl = pointer(mc);
    mc.size = sizeof(mc)
    mlc.sizecontrol = sizeof(mc);
    result = windll.winmm.mixerGetLineControlsA(handle ,
        byref(mlc), MIXER_GETLINECONTROLSF_ONEBYTYPE);
    if result:  return result

    mcd = MIXERCONTROLDETAILS()
    memset(byref(mcd),0,sizeof(mcd))
    volume_obj = DWORD(controlvalue)
    mcd.size = sizeof(mcd)
    mcd.pdetail = pointer(volume_obj)
    mcd.controlid = mc.id
    mcd.detailsize = sizeof(DWORD)
    mcd.channels = 1
    result = windll.winmm.mixerSetControlDetails(handle,
         byref(mcd), MIXER_SETCONTROLDETAILSF_VALUE);
    return result


def scrub_html(text, a=True, a_list=False, hr=False, img_list=False, title=False):
    '''
        Remove HTML markup from a given text string.

        Argument:
            text            - The given HTML text to scrub.
        Options:
            a               - Include linked text.
            a_list          - Include links list at end of document.
            hr              - Render header rules.
            img_list        - Include image list at end of document.
            title           - Include title text.
        Returns:
            A plain text representation of the html file.
    '''
    from sgmllib import SGMLParser
    if not hasattr(SGMLParser, 'htmlscrub'):  # prevent multiple exec
        class htmlscrub(SGMLParser):
            def reset(self):
                self.pieces = []
                self.imgs = []
                self.links = []
                self.dumpdata = False
                self.orderedli = False
                self.listnum = 1
                SGMLParser.reset(self)

            def newline(self, attrs=[]):
                self.pieces.append('\n')
            def ignore(self, attrs=None): pass

            do_br = newline
            start_dl = end_dl = end_dt = newline
            start_dt = ignore
            start_h1 = end_h1 = start_h2 = end_h2 = newline
            start_h3 = end_h3 = start_h4 = end_h4 = newline
            start_h5 = end_h5 = start_h6 = end_h6 = newline
            start_ol = end_ol = newline
            start_p = end_p = newline
            start_pre = end_pre = newline
            start_th = end_th = newline
            start_tr = end_tr = newline
            start_ul = end_ul = newline

            def start_a(self, attrs):
                self.dumpdata = not a
                if a_list:
                    href = [v for k, v in attrs if k=='href']
                    if href:  self.links.append('Link[%s]:   %s' % (
                        len(self.links)+1, href[0]) )
            def end_a(self):
                self.dumpdata = False
                if a_list:  self.pieces.append('[%s]' % len(self.links))

            def do_hr(self, attr):
                if hr: self.pieces.append('\n%s\n' % ('_' * 72))
                else: self.newline()

            def do_img(self, attrs):
                if img_list:
                    src = [v for k, v in attrs if k=='src']
                    alt = [v for k, v in attrs if k=='alt']
                    if src:
                        s = 'Image{%s}:  %s' % (len(self.imgs)+1, src[0])
                        if alt: s = '%s "%s"' % (s, alt[0])
                        self.imgs.append(s)
                        self.pieces.append('{%s}' % len(self.imgs))

            def start_li(self, attrs):
                if self.orderedli:  self.pieces.append('\t%s. ' % self.listnum)
                else:               self.pieces.append('\t* ')
                self.listnum += 1
            end_li = newline

            def start_script(self, attrs):  self.dumpdata = True
            def end_script(self):           self.dumpdata = False
            def start_style(self, attrs):   self.dumpdata = True
            def end_style(self):            self.dumpdata = False

            def start_title(self, attrs):
                self.dumpdata = not title
                if title: self.pieces.append('[')
            def end_title(self):
                self.dumpdata = False
                if title: self.pieces.append(']\n\n')

            def start_ol(self, attrs):
                self.orderedli = True
                self.listnum = 1
                self.newline()
            def end_ol(self):           self.orderedli = False

            # ---------------------------------------------------------
            def handle_data(self, text):
                if not self.dumpdata:
                    self.pieces.append(' '.join(text.split()) ) # normalize ws

            def output(self):
                'Return processed HTML as a single string.'
                tempstr = ' '.join( [ x for x in self.pieces if x <> '' ] )
                if ' , ' in tempstr:
                    tempstr.replace(' , ', ', ')
                if self.links:
                    tempstr += '\n'
                    tempstr += '\n\n' + '\n'.join(self.links)
                if self.imgs:
                    tempstr += '\n'
                    tempstr +=   '\n' + '\n'.join(self.imgs)
                return tempstr
        SGMLParser.htmlscrub = htmlscrub      # add to module for next time

    parser = SGMLParser.htmlscrub()
    parser.feed(text)
    parser.close()

    _log.debug('called.')
    return parser.output()


def start_svc(name):
    '''
        Start the specified Windows service if it is currently stopped.

        Arguments:
            name            - The short service name.
    '''
    try:
        import win32service as svc, win32serviceutil as svcu
        status = svcu.QueryServiceStatus(name)[1]
        if status == svc.SERVICE_STOPPED:
            _log.warn('Attempting to start "%s" service ...' % name)
            svcu.StartService(name)
            tries = 10
            while tries:
                time.sleep(1)  # wait up to 10 seconds
                status = svcu.QueryServiceStatus(name)[1]
                if status == svc.SERVICE_RUNNING: break
                tries = tries - 1
            time.sleep(5)  # wait a bit, so service may get ready.
            _log.debug('"%s" service started without error.' % name)
    except Exception, e:
         _log.error('Could not start "%s" service.\n%s' % (
             name, traceback.format_exc()) )


def stop_svc(name):
    '''
        Stop the specified Windows service if it is currently started.

        Arguments:
            name            - The short service name.
    '''
    try:
        import win32service as svc, win32serviceutil as svcu
        status = svcu.QueryServiceStatus(name)[1]
        if status == svc.SERVICE_RUNNING:
            _log.warn('Attempting to stop "%s" service ...' % name)
            svcu.StopService(name)
            tries = 10
            while tries:
                time.sleep(1)  # wait up to 10 seconds
                status = svcu.QueryServiceStatus(name)[1]
                if status == svc.SERVICE_STOPPED: break
                tries = tries - 1
            _log.debug('"%s" service stopped without error.' % name)
    except Exception, e:
         _log.error('Could not stop "%s" service.\n%s' % (
             name, traceback.format_exc()) )


def restart_svc(name):
    '''
        Restarts a Windows Service.
        Arguments:
            name            - The short service name.
    '''
    stop_svc(name)
    time.sleep(1)
    start_svc(name)


def suspend_screen(switch):
    '''
        Send a message to the screen with DPMS to toggle its power save mode.

        Arguments:
            switch:
                True, 1     - Enable power saver mode.
                False, 0    - Power up the screen.
        Notes:
            To suspend:
                The Scala Player constantly forces the screen on, so it must be
                told to exit or be minimized previously for this call to succeed.
            To resume:
                Start the player, then call this function again if necessary.
            It is easiest to acomplish these tasks from CM Maintenance jobs.
    '''
    import win32gui
    _log.info(str(switch))
    if switch:
        win32gui.SendMessage(-1, 0x112, 0xf170, 2)    # DPMS turn off
    else:
        win32gui.SendMessage(-1, 0x112, 0xf170, -1)   # DPMS turn on


def time_in_range(timestr=None, timefmt=None, timestamp=None, **time_range):
    '''
        Checks whether a given time is between now and a +/- time range.

        (-Range is negative)             Now           (+Range is positive)
            begin  |<----------------- end|begin ----------------->| end
            False  |       True           |           True         | False

        Arguments/Options:
            timestr     - A date/time string,             e.g.: '4/7/09 12:00'
            timefmt     - A guide to parse the string,    e.g.: '%m/%d/%y %H:%M'
                          http://docs.python.org/library/time.html#time.strftime
            timestamp   - a time in seconds, e.g. from time.time(), or os.stat()
            time_range  - See file_is_current()
        Returns:
            True if a given date/time is within range, False if not.
        Notes:
            One and only one of timestr or timestamp must be passed.
        Examples:
            See auto_csv() example 3.
    '''
    if (timestr is None and timestamp is None) or (timestr and timestamp):
        raise TypeError, 'One of {timestr, timestamp} must be passed, not both.'
    if not time_range:  raise TypeError, 'time_range required.'

    from datetime import datetime, timedelta
    if timestr:
        giventime = datetime.strptime(timestr, timefmt)
    else:
        giventime = datetime.fromtimestamp(timestamp)

    # check if time meets criteria
    now = datetime.now()
    range = timedelta(**time_range)
    if range.days < 0:
        begin = now + range
        end = now
    else:
        begin = now
        end = now + range

    if begin <= giventime <= end:
        _log.debug('time is within range.')
        return True
    else:
        _log.debug('time not in range.')
        return False


def unpack(filename, overwrite=True, pwd=None, dest=None, addbase=True):
    '''
        Extracts an archive file of type (zip, gz, bz2, tar, tar.gz, tar.bz2),
        to the folder where it exists.

        Arguments:
            filename        - A filename to search for, using find_file().
        Options:
            overwrite       - Whether to overwrite existing files.
            pwd             - A zip password, if needed.
            dest            - An alternative destination to extract to.
            addbase         - Extract files into a folder named with the
                              basename of the archive.
        Notes:
            If an extracted file is an archive, it will be unpacked as well.
        Example:
            from scalatools import unpack
            unpack(svars.filename)
    '''
    from os.path import splitext
    filename = find_file(filename)
    arctypes = ('.zip','.gz','.bz2','.tar')
    blocksize = 8192
    basename = os.path.basename(filename).lower()
    rootpath, extension = splitext(filename)  # only removes last ext
    if dest:
        if addbase:  # remove extension from basename and join to dest
            rootpath = join(dest, splitext(os.path.basename(filename))[0])
        else:
            rootpath = dest
    if basename.endswith('.zip'):           arctype = 'zip'
    elif basename.endswith('.gz'):          arctype = 'gz'
    elif basename.endswith('.bz2'):         arctype = 'bz2'
    elif basename.endswith('.tar'):         arctype = 'tar'
    elif basename.endswith('.tar.gz'):      arctype = 'tar'
    elif basename.endswith('.tgz'):         arctype = 'tar'
    elif basename.endswith('.tar.bz2'):     arctype = 'tar'
    elif basename.endswith('.tbz2'):        arctype = 'tar'
    else:
        raise TypeError, 'unknown file type: %s' % basename

    def is_archive(path):
        return splitext(path)[1].lower() in arctypes

    if arctype == 'zip':
        import zipfile
        zip = zipfile.ZipFile(filename, 'r')
        if pwd: zip.setpassword(pwd)

        # extract the file into a folder of the same basename
        if not os.path.exists(rootpath):  os.mkdir(rootpath)

        for zippedfile in zip.namelist():
            outpath = join(rootpath, zippedfile)
            dirname = os.path.dirname(outpath)
            if not os.path.exists(dirname): #  need to create dir with zip
                _log.debug('mkdir %s' % dirname)
                os.makedirs(dirname)
            if os.path.isdir(outpath): continue

            if os.path.exists(outpath):
                if overwrite and os.path.isfile(outpath):
                    _log.debug('deleting %s' % outpath)
                    os.unlink(outpath)
                else:
                    _log.debug('skipping %s' % outpath)
                    continue  # to next file

            _log.info('extracting %s' % outpath)
            zip.extract(zippedfile, path=rootpath)

            if is_archive(zippedfile):
                unpack(outpath, overwrite=overwrite, pwd=pwd)
        zip.close()
        return

    if arctype == 'tar':
        import tarfile
        if not os.path.exists(rootpath):  os.mkdir(rootpath)
        tar = tarfile.TarFile(filename)
        for member in tar.getmembers():
            outpath = join(rootpath, member.name)

            if os.path.exists(outpath):
                if overwrite and os.path.isfile(outpath):
                    _log.debug('deleting %s' % outpath)
                    os.unlink(outpath)
                else:
                    _log.debug('skipping %s' % outpath)
                    continue  # to next file

            _log.info('extracting %s' % outpath)
            tar.extract(member, path=rootpath)
            if is_archive(member.name):
                unpack(outpath, overwrite=overwrite)
        tar.close()
        return

    if os.path.exists(rootpath):
        if overwrite and os.path.isfile(rootpath):
            _log.debug('deleting  %s' % rootpath)
            os.unlink(rootpath)
        else:
            _log.debug('skipping  %s' % rootpath)
            return

    if arctype == 'gz':
        import gzip
        fin = gzip.GzipFile(filename, 'rb')

    elif arctype == 'bz2':
        import bz2
        fin = bz2.BZ2File(filename, 'rb')

    # write gz or bz2 file
    _log.info('extracting %s' % rootpath)
    fout = file(rootpath, 'wb')
    while True:
        block = fin.read(blocksize)
        if not block: break
        fout.write(block)
    fin.close()
    fout.close()

    if is_archive(rootpath):
        unpack(rootpath, overwrite=overwrite) # e.g.  .tar.gz


def wait_key(prompt='\nHit any key to exit ... '):
    '''
        Wait for a keypress at the console.
        Modifier keys are not handled until a standard key is pressed in
        combination.  Useful to prevent utility scripts from disappearing.
        Returns:
            The key pressed.  If a function key is pressed, (e.g. F2, Delete)
            this function must be called twice.
    '''
    try:                    # Win32
        from msvcrt import getch
    except ImportError:     # UNIX
        def getch():
            import tty, termios
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                return sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
    print prompt,
    key = getch()
    print key
    return key


def zip_it(fileset, zipfilename, mode='w', root=None, compression=True):
    '''
        Creates a pkzip format archive.

        Arguments:
            fileset         - A single or list of filenames to archive, or
                              a list of (filename, arcname) pairs.
            zipfilename     - Output archive filename.
        Options:
            mode            - 'w' (write) or 'a' (append).
            root            - remove this root folder from each path to create
                              relative paths inside the archive.
            compression     - Use zlib.ZIP_DEFLATE to compress files.
        Example:
            from scalatools import zip_it
            ...
            zip_it(glob(fspec), tempfilename, root=r'f:\data\')
    '''
    if fileset and zipfilename:
        import zipfile
        if type(fileset) not in (list, tuple):
            fileset = [fileset]

        z = zipfile.ZipFile(zipfilename, mode, compression=zipfile.ZIP_DEFLATED)
        for fn in fileset:
            arcname = None
            if type(fn) is tuple:
                fn, arcname = fn
            elif root:
                arcname = fn.replace(root, '')
            if os.access(fn, os.R_OK):
                z.write(fn, arcname=arcname)
            else:
                _log.warning('"%s" not available.' % fn)
        z.close()
    else:
        errstr = 'parameters incorrect: %s' % locals()
        _log.error(errstr)


if __name__ == '__main__':                      # Run from command line
    import types
    from optparse import OptionParser
    ERR_CMDL = 2
    ERR_EXCP = 3
    ERR_UNKN = 4

    # make a list of functions to be available from the command line
    ftype = types.FunctionType
    _functions = dict([ (k, globals()[k])   # (name, function)
                        for k in globals().keys()
                        if type(globals()[k]) is ftype
                        if not k.startswith('_')
                        if not k == 'COMObject'
                        ]);  del k
    fnames = _functions.keys()
    fnames.sort()

    parser = OptionParser(usage=__doc__, version=__version__)
    parser.add_option('-q', '--query-function', metavar='FNAME',
        help='Query the arguments of a function.\nOne of:\n%s' %
        ', '.join(fnames) )
    parser.add_option('-v', '--verbose', action='store_true',
        help='Enable verbose output.')
    parser.add_option('-V', '--very-verbose', action='store_true',
        help='Enable debugging output.')
    (opts, args) = parser.parse_args()

    # validate/transform arguments
    loglevel = 'warn'
    if opts.verbose:  loglevel = 'info'
    if opts.very_verbose:  loglevel = 'debug'
    log2 = sl.get_logger(level=loglevel)
    typemap = {'None':None, 'True':True, 'False':False}
    for i,arg in enumerate(args):
        if arg in typemap:
            args[i] = typemap[arg]
        elif arg.isdigit():
            args[i] = int(arg)
        elif arg[0] == '\\' and arg[1] != '\\':  # a way to escape the int()
            args[i] = args[i][1:]

    if opts.query_function:
        from inspect import getargspec
        if opts.query_function in _functions:
            func = _functions.get(opts.query_function)
            args, defs = getargspec(func)[0:4:3]
            if type(defs) not in (list, tuple): defs = (defs,)  # :/

            params = []  # zip the args with the defs, backwards
            diff = len(args) - len(defs)
            for i,arg in enumerate(args):
                if i < diff:  params.append(arg)
                else:         params.append('%s=%s' % (args[i], defs[i-diff]) )
            if len(params) == 0:
                print 'No arguments to this function.'
            else:
                print '  %s:' % opts.query_function, ', '.join(params)
        else:
            log2.error('unknown function: ' + opts.query_function)
            sys.exit(ERR_UNKN)
    else:
        if args:
            if args[0] in _functions:
                try:
                    result = _functions.get(args[0])(*args[1:])
                    if type(result) in (str, unicode):  print result
                    else:                               sys.exit(result)
                except Exception, e:
                    errstr = '%s: %s' % (e.__class__.__name__, e)
                    log2.debug(errstr)  # likely already logged :/
                    sys.exit(ERR_EXCP)
            else:
                log2.error('unknown function: ' + args[0])
                sys.exit(ERR_UNKN)
        else:
            parser.print_help()
            sys.exit(ERR_CMDL)

