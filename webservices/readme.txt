
scws.py - (C) 2008 Scala, Inc., Mike Miller
    Requires: soaplib.py

How to use this module:

1) Decide on a function to use, e.g.:

    https://developer.scala.com/dev/index.php/PlayerRS.list


2) Figure out the service name (easy):

    The "player" service is the one needed, you can also get these names from here:
    http://host:port/ContentManager/api/

    The ServiceRS form can also be used, e.g. "PlayerRS"


3) Write some code:
    ---------
    import scws
    hoststr    = 'services.scala.com:8082'
    baseurl    = 'http://%s/ContentManager/' % hoststr
    authstr    = 'user:pass'
    
    # Create a Content Manager object
    cm = scws.ConManager(baseurl, authstr)

    players = cm.player.list()  # ContentManager.servicename.funcname()
    ---------


3a) Use dictionaries or "Transfer Objects" to send parameters if desired:
    ---------
    src = scws.TObj(column='revision')                # keywords or
    src.restriction  = 'GREATER_THAN'                 # attributes may be used
    src.value        = 3

    src2 = scws.TObj(column='revision', restriction='LESS_THAN', value=5)

    templates = cm.template.list(searchCriteria=[src,src2])  # execute function

    # Override the arg (tag name) using a keyword arg:
    # cm.uploadfile.requestUpload(arg0=RequestFileTO)
    ---------


3b) How to configure a logging channel to get more information from scws:

    import scalalib
    log = scalalib.get_logger(level='debug', con=True, 
        format=' %(levelname)s %(message)s')
    # now continue with scws ...
    
4) Returned objects (like players/templates above) are simply a list of python
   objects representing the objects (or tags) returned, and easy to use. e.g.:

    for template in templates:
        print ' *', template.name


5) Next, see the _test examples included, and also the tutorial at:

    https://developer.scala.com/dev/index.php/WebServicesTutorial



To Do:
-----------------------------
  *  https support
  *  urllib2 support from py 2.3 ++

