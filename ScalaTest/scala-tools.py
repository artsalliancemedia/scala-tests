'''
Created on 26 Jul 2013

@author: Tobias Fischer
'''

import webservices.scws as scws
import json
import os

def main():
    #read config file
    try:
        config = json.load(open(os.path.join(os.path.dirname(__file__), u'settings.json'), 'r'))
    except IOError:
        raise IOError('The settings.json file does not exist')
        
    baseurl = config[u"baseurl"]
    authstr = config[u"authstring"]
            
    # Create a Content Manager object, then use
    content_manager = scws.ConManager(baseurl, authstr, api_vers='v1.2')
    players = content_manager.PlayerRS.list()
    for player in players:
        print 'Player:', player.name
    
#     #list current playlists
#     playlists = content_manager.PlaylistRS.list()
#     if playlists:
#         print 'Playlist list ...'
#         for playlist in playlists:
#             print '  *', playlist.name, ', id:', playlist.id
#     else:
#         print 'No playlists found.'
#     print
#      
#     #list all messages
#     messages = content_manager.MessageRS.list()
#     if messages:
#         print 'Message list ...'
#         for message in messages:
#             print '  *', message.name
#     print

    #delete playlist from previous run
    playlist_filter = scws.TObj()
    playlist_filter.column       = 'name'
    playlist_filter.restriction  = 'EQUALS'
    playlist_filter.value        = 'Tobias Playlist'
    
    playlists_to_delete = content_manager.PlaylistRS.list(searchCriteria=playlist_filter)
    for playlist_to_delete in playlists_to_delete:
        content_manager.PlaylistRS.delete(playlistId=playlist_to_delete.id)
        print 'Deleted old playlist ID:', playlist_to_delete.id

    #upload media
    file_id = content_manager.upload_file('test_image.png', 'CADIENLOBBY')
    print 'File ID:', file_id
     
    #create playlist
    new_pl = scws.TObj()
    new_pl.name = 'Tobias Playlist'
    new_pl.description = 'Test Scala API'
    uploaded_pl = content_manager.PlaylistRS.create(playlistTO=new_pl)
    print 'Playlist ID:', uploaded_pl[0].id
     
    #fill playlist
    pl_item = scws.TObj()
    pl_item.mediaId = file_id
    pl_item.duration = 10
     
    uploaded_pl_item = content_manager.PlaylistRS.addPlaylistItem(playlistId=uploaded_pl[0].id, playlistItem=pl_item)
    print 'PlaylistItem ID:', uploaded_pl_item[0].id
    
    #create schedule
    #first get channel
    our_channel_criteria = scws.TObj(column='name', restriction='EQUALS', value='3x1 1600x900')
    our_channel = content_manager.ChannelRS.list(searchCriteria = our_channel_criteria)
    print 'Channel ID:', our_channel[0].id
    print 'Channel Name:', our_channel[0].name
    
    #get all frames from channel
    frames = content_manager.ChannelRS.getFrames(channelId=our_channel[0].id)
    print 'Frame ID:', frames[0].id
    print 'Frame name:', frames[0].name
    
    #remove old timeslots for frame
    timeslots = content_manager.ChannelRS.getTimeslots( {'channelId':our_channel[0].id}, frameId=frames[0].id)
    for timeslot in timeslots:
        content_manager.ChannelRS.deleteTimeslot(timeslotId=timeslot.id)
        print 'Deleted old new_timeslot ID:', timeslot.id
    
    #create new timeslot data
    new_timeslot = scws.TObj()
    new_timeslot.channelId = our_channel[0].id
    new_timeslot.frameId = frames[0].id
    new_timeslot.playlistId = uploaded_pl[0].id
    new_timeslot.startDate = '2013-07-30'
    new_timeslot.endDate = '2013-08-30'
    new_timeslot.startTime = '00:00:00'
    new_timeslot.endTime = '23:59:59'
    new_timeslot.playFullScreen = False
    new_timeslot.recurrencePattern = 'WEEKLY'
    new_timeslot.weekdays = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY','SUNDAY']
    new_timeslot.color = '#FF0000'
    new_timeslot.locked = False
    
    #upload timeslot
    uploaded_timeslot = content_manager.ChannelRS.createTimeslot(timeslotParam=new_timeslot)
    print 'Schedule ID:', uploaded_timeslot[0].id
    print 'Schedule Name:', uploaded_timeslot[0].name
    
    #update display
    displays = content_manager.PlayerRS.getPlayerDisplays(playerId=players[0].id)
    print 'Display ID:', displays[0].id
    print 'Display Name:', displays[0].name
    
    updated_display = scws.TObj()
    updated_display.id = displays[0].id
    updated_display.screenCounter = 1
    updated_display.description = 'Tobias is updating a screen'
    updated_display.channelId = our_channel[0].id
    
    content_manager.PlayerRS.updatePlayerDisplay(playerDisplay=updated_display)
    
    #generate plan so player can sync
    distribution_server_tasks = content_manager.PlanGeneratorRS.generatePlans(playerIds=[players[0].id])
    #for server in distribution_server_tasks:
    #    print content_manager.PlanGeneratorRS.getPlanStatus(uuid=server.uuid)
        
if __name__ == '__main__':
    main()