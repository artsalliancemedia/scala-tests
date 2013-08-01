#!/usr/bin/env python
'''
    Short script to demonstrate the scws module/class.
'''
import sys
import scws
import scalalib

# update these to the correct values
hoststr = 'cm.yourco.com:8080'
baseurl = 'http://%s/ContentManager/' % hoststr
authstr = 'scalaweb:pword'
debug   = True   # enables verbose info printed to console
debug   = False  # disables verbose info printed to console, Ctrl+T to flip

log = scalalib.get_logger(level='debug' if debug else 'warn')

# can override password on the command line
if len(sys.argv) > 1:   authstr = sys.argv[1]

# First, create a Content Manager object
cm = scws.ConManager(baseurl, authstr)

#  Examples below
do_test = [True, False, False, False, False, False]
do_test.insert(0, None)  # 1 based

#
#  1. Simple player listing
#  ----------------------------------------------------------------------
if do_test[1]:

    print '\nPlayer list ...'
    players = cm.player.list()

    for player in players:
        print '  * Name: ', player.name
    print

    # save last player for later
    playerid = player.id
    playername = player.name


#
#  2. Playlist search test, with error checking
#  ----------------------------------------------------------------------
if do_test[2]:

    src = scws.TObj(column='name')
    src.restriction  = 'EQUALS'
    src.value        = 'Grocery'

    playlists = cm.playlist.list(searchCriteria=src)
    if playlists:
        print 'Playlist list ...'
        for playlist in playlists:
            print '  *', playlist.name, ', id:', playlist.id
    else:
        print 'No playlists found named %s.' % src.value
    print


#
#  3. Get player metadata test
#  ----------------------------------------------------------------------
if do_test[3]:

    def getmd(mdname, playerid):
        'Given a player id and a metadata name, returns its value.'
        # search for metadata id by name
        # can populate TO inline with keyword args
        src = scws.TObj(column='name', restriction='EQUALS',
            value=mdname)
        mlist = cm.player.listMeta(searchCriteria=src)

        if mlist:  # this id refers to the metadata name only
            metadataid = mlist[0].id
        else:  return None

        # get values
        mlist = cm.player.getMetaValues(playerId=playerid)

        # find the value with the matching metadata name id, else None
        for metavalue in mlist:
            if metavalue.metadataId == metadataid:
                return metavalue.value

    # playerid comes from first test
    mdname = 'Player.postalcode'
    value = getmd(mdname, playerid)
    print mdname, 'on', playername, '=', value
    print


#
#  4. Media metadata creation test
#  ----------------------------------------------------------------------
if do_test[4]:

    mdata = scws.TObj()
    mdata.type              = 'INTEGER'
    mdata.allowedValues     = 'ANY'
    name                    = 'scws_created_metadata'

    count = 1
    while True:
        try:
            mdata.name = name + str(count)
            results = cm.media.createMeta(meta=mdata)[0]
            print 'Created metadata:'
            print '  ', results
            break # on success
        except ValueError, nae:
            count += 1
            if count >= 10: break


#
#  5. Player metadata set test
#  ----------------------------------------------------------------------
if do_test[5]:

    item = 346734 #   'scws mikez player2' , 346734
    mdname = 'Player.postalcode'
    try:
        print cm.set_metaval(item, mdname, 19341) # 91367 19341 123456
    except:
        print cm.set_metaval(item, mdname, 91367) # 91367 19341 123456

