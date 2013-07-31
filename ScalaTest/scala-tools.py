'''
Created on 26 Jul 2013

@author: Tobias Fischer
'''

import webservices.scws as scws
import json
import os

def print_playlists():
    #list current playlists
    playlists = content_manager.PlaylistRS.list()
    if playlists:
        print 'Playlist list ...'
        for playlist in playlists:
            print '  *', playlist.name, ', id:', playlist.id
    else:
        print 'No playlists found.'
    print
      
def print_messages():
    #list all messages
    messages = content_manager.MessageRS.list()
    if messages:
        print 'Message list ...'
        for message in messages:
            print '  *', message.name
    else:
        print 'No messages found'
    print
    
def get_player():
    players = content_manager.PlayerRS.list()
    for player in players:
        print u'Player:', player.name
    return players[0].id

def create_frameset_if_not_exists(frameset_name):
    frameset_id = None
    frameset_filter = scws.TObj()
    frameset_filter.column       = u'name'
    frameset_filter.restriction  = u'EQUALS'
    frameset_filter.value        = frameset_name
    our_framesets = content_manager.ChannelRS.listFramesets(searchCriteria=frameset_filter)
    
    #frameset already existing
    if(our_framesets):
        frameset_id = our_framesets[0].id
        
    #frameset not existing yet, create frameset and add frames
    else:
        new_frameset = scws.TObj()
        new_frameset.name = frameset_name
        new_frameset.screenWidth = 3200
        new_frameset.screenHeight = 1800
        
        new_frame1 = scws.TObj()
        new_frame1.name = u'Tobias Frame 1'
        new_frame1.x = 0
        new_frame1.y = 0
        new_frame1.width = 1600
        new_frame1.height = 900
        new_frame1.autoscale = u'FIT_INSIDE'
        
        new_frame2 = scws.TObj()
        new_frame2.name = u'Tobias Frame 2'
        new_frame2.x = 1600
        new_frame2.y = 0
        new_frame2.width = 1600
        new_frame2.height = 900
        new_frame2.autoscale = u'FIT_INSIDE'
        
        new_frame3 = scws.TObj()
        new_frame3.name = u'Tobias Frame 3'
        new_frame3.x = 0
        new_frame3.y = 900
        new_frame3.width = 1600
        new_frame3.height = 900
        new_frame3.autoscale = u'FIT_INSIDE'
        
        new_frame4 = scws.TObj()
        new_frame4.name = u'Tobias Frame 4'
        new_frame4.x = 1600
        new_frame4.y = 900
        new_frame4.width = 1600
        new_frame4.height = 900
        new_frame4.autoscale = u'FIT_INSIDE'
        
        #warning: first frame is a parameter of createFrameset
        uploaded_frameset = content_manager.ChannelRS.createFrameset(frameset=new_frameset, frame=new_frame1)
        frameset_id = uploaded_frameset.id
        
        #warning: other frames must be added to frameset after creating frameset
        content_manager.ChannelRS.createFrame(framesetId=frameset_id, frame=new_frame2)
        content_manager.ChannelRS.createFrame(framesetId=frameset_id, frame=new_frame3)
        content_manager.ChannelRS.createFrame(framesetId=frameset_id, frame=new_frame4)
    
    return frameset_id

def delete_and_create_playlist(playlist_name):
    #delete playlist from previous run
    playlist_filter = scws.TObj()
    playlist_filter.column       = u'name'
    playlist_filter.restriction  = u'EQUALS'
    playlist_filter.value        = playlist_name
    
    playlists_to_delete = content_manager.PlaylistRS.list(searchCriteria=playlist_filter)
    for playlist_to_delete in playlists_to_delete:
        content_manager.PlaylistRS.delete(playlistId=playlist_to_delete.id)
        print u'Deleted old playlist ID:', playlist_to_delete.id
        
    #create playlist
    #warning: name has to different from current playlists otherwise an exception occurs
    new_pl = scws.TObj()
    new_pl.name = playlist_name
    new_pl.description = u'Test Scala API'
    uploaded_pl = content_manager.PlaylistRS.create(playlistTO=new_pl)
    
    return uploaded_pl[0].id

def create_channel_if_not_exists(channel_name, frameset_id):
    channel_id = None
    channel_filter = scws.TObj()
    channel_filter.column       = u'name'
    channel_filter.restriction  = u'EQUALS'
    channel_filter.value        = channel_name
    
    our_channels = content_manager.ChannelRS.list(searchCriteria=channel_filter)
    if(our_channels):
        channel_id = our_channels[0].id
    else:
        new_channel = scws.TObj()
        new_channel.name = channel_name
        new_channel.description = u'This channel was created with the Scala scws lib'
        new_channel.framesetId = frameset_id
        uploaded_channel = content_manager.ChannelRS.create(channel=new_channel)
        channel_id = uploaded_channel[0].id
        
    return channel_id

def main():
    #read config file
    try:
        config = json.load(open(os.path.join(os.path.dirname(__file__), u'settings.json'), u'r'))
    except IOError:
        raise IOError(u'The settings.json file does not exist')
        
    baseurl = config[u"baseurl"]
    authstr = config[u"authstring"]
            
    # Create a Content Manager object, then use
    global content_manager
    content_manager = scws.ConManager(baseurl, authstr, api_vers=config[u"api"])    
    
    player_id = get_player()
    
    #upload media
    file_id = content_manager.upload_file(u'test_image.png', config[u"network"])
    print u'File ID:', file_id
    
    frameset_id = create_frameset_if_not_exists(u'Tobias Frameset 1')
    print u'Frameset ID:', frameset_id
    channel_id = create_channel_if_not_exists(u'Tobias Channel 1', frameset_id)
    print u'Channel ID:', channel_id
    playlist_id = delete_and_create_playlist('Tobias Playlist')
    print u'Playlist ID:', playlist_id
    
    #fill playlist
    pl_item = scws.TObj()
    pl_item.mediaId = file_id
    pl_item.duration = 10
     
    uploaded_pl_item = content_manager.PlaylistRS.addPlaylistItem(playlistId=playlist_id, playlistItem=pl_item)
    
    #create schedule
    
    #get all frames from channel
    frames = content_manager.ChannelRS.getFrames(channelId=channel_id)
    for frame in frames:
        print u'Frame ID:', frame.id
        print u'Frame name:', frame.name
    
    #remove old time slots for frame
    #warning: if old time slots are not removed overlapping occurs
    #warning: channelId has to be in an array (this conflicts with documentation)
    timeslots = content_manager.ChannelRS.getTimeslots( {u'channelId':channel_id}, frameId=frames[0].id)
    for timeslot in timeslots:
        content_manager.ChannelRS.deleteTimeslot(timeslotId=timeslot.id)
        print u'Deleted old timeslot ID:', timeslot.id
    
    #create new time slot data
    new_timeslot = scws.TObj()
    new_timeslot.channelId = channel_id
    new_timeslot.frameId = frames[0].id
    new_timeslot.playlistId = playlist_id
    new_timeslot.startDate = u'2013-07-30'
    new_timeslot.endDate = u'2013-08-30'
    new_timeslot.startTime = u'00:00:00'
    new_timeslot.endTime = u'23:59:59'
    new_timeslot.playFullScreen = False
    new_timeslot.recurrencePattern = u'WEEKLY'
    new_timeslot.weekdays = [u'MONDAY', u'TUESDAY', u'WEDNESDAY', u'THURSDAY', u'FRIDAY', u'SATURDAY', u'SUNDAY']
    new_timeslot.color = u'#FF0000'
    new_timeslot.locked = False
    
    #upload time slot
    uploaded_timeslot = content_manager.ChannelRS.createTimeslot(timeslotParam=new_timeslot)
    print u'Schedule ID:', uploaded_timeslot[0].id
    print u'Schedule Name:', uploaded_timeslot[0].name
    
    #update display
    displays = content_manager.PlayerRS.getPlayerDisplays(playerId=player_id)
    print u'Display ID:', displays[0].id
    
    updated_display = scws.TObj()
    updated_display.id = displays[0].id
    updated_display.screenCounter = 1
    updated_display.description = u'Tobias is updating a screen'
    updated_display.channelId = channel_id
    
    content_manager.PlayerRS.updatePlayerDisplay(playerDisplay=updated_display)
    
    #generate plan so player can sync
    distribution_server_tasks = content_manager.PlanGeneratorRS.generatePlans(playerIds=[player_id])
    #for server in distribution_server_tasks:
    #    print content_manager.PlanGeneratorRS.getPlanStatus(uuid=server.uuid)
        
if __name__ == u'__main__':
    main()