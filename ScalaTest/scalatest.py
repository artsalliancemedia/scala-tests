'''
Created on 26 Jul 2013

@author: Tobias Fischer
'''

import webservices.scws as scws

if __name__ == '__main__':
    baseurl = 'http://aam-scalaplayer-test:8080/ContentManager/'
    authstr = 'CMWeb:liggunna'
    # Create a Content Manager object, then use
    cm = scws.ConManager(baseurl, authstr, api_vers='v1.2')
    players = cm.PlayerRS.list()
    for player in players:
        print 'Player:', player.name
    
#     playlists = cm.PlaylistRS.list()
#     if playlists:
#         print 'Playlist list ...'
#         for playlist in playlists:
#             print '  *', playlist.name, ', id:', playlist.id
#     else:
#         print 'No playlists found.'
#     print
#     
#     messages = cm.MessageRS.list()
#     if messages:
#         print 'Message list ...'
#         for message in messages:
#             print '  *', message.name
#     print

    #upload media
    fileID = cm.upload_file('image.png', 'CADIENLOBBY')
    print 'File ID:', fileID
     
    #create playlist
    newpl = scws.TObj()
    newpl.name = 'Tobias Playlist'
    newpl.description = 'Test Scala API'
    uploaded_pl = cm.PlaylistRS.create(playlistTO=newpl)
    print 'Playlist ID:', uploaded_pl[0].id
     
    #fill playlist
    plitem = scws.TObj()
    plitem.mediaId = fileID
    plitem.duration = 10
     
    uploaded_plitem = cm.PlaylistRS.addPlaylistItem(playlistId=uploaded_pl[0].id, playlistItem=plitem)
    print 'PlaylistItem ID:', uploaded_plitem[0].id
    
    #create schedule
    ourchannelcriteria = scws.TObj(column='name', restriction='EQUALS', value='3x1 1600x900')
    ourchannel = cm.ChannelRS.list(searchCriteria = ourchannelcriteria)
    print 'Channel ID:', ourchannel[0].id
    
    frames = cm.ChannelRS.getFrames(channelId=ourchannel[0].id)
    print 'Frame ID:', frames[0].id
    print 'Frame name:', frames[0].name
    
    timeslot = scws.TObj()
    timeslot.channelId = ourchannel[0].id
    timeslot.frameId = frames[0].id
    timeslot.playlistId = uploaded_pl[0].id
    timeslot.startDate = '20130730'
    timeslot.endDate = '20130830'
    timeslot.startTime = '00:00:00'
    timeslot.endTime = '23:59:59'
    timeslot.playFullScreen = False
    timeslot.recurrencePattern = 'WEEKLY'
    timeslot.weekdays = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY']
    timeslot.color = '#ccccff'
    timeslot.locked = False
    
    uploaded_timeslot = cm.ChannelRS.createTimeslot(timeslotParam=timeslot)
    print 'Schedule ID:', uploaded_timeslot[0].id
    
    displays = cm.PlayerRS.getPlayerDisplays(playerId=players[0].id)
    print 'Display ID:', displays[0].id
    
    displayupdate = scws.TObj()
    displayupdate.id = displays[0].id
    displayupdate.screenCounter = 1
    displayupdate.description = 'Tobias is updating a screen'
    displayupdate.channelId = ourchannel[0].id
    
    uploaded_playerdisplay = cm.PlayerRS.updatePlayerDisplay(playerDisplay=displayupdate)