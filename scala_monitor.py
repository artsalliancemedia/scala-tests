import webservices.scws as scws
import json
import os

def human_filesize(filesize):
    """Takes a number of bytes and converts it to a human readable value.
    Eg: 157456 -> 153.7 KB
    """
    for suffix in ['bytes','KB','MB','GB']:
        if filesize < 1024.0 and filesize > -1024.0:
            return "%3.1f%s" % (filesize, suffix)
        filesize /= 1024.0
    return "%3.1f%s" % (filesize, 'TB')


class ScalaMonitor:
    def __init__(self, baseurl, authstr, api):
        self.content_manager = scws.ConManager(baseurl, authstr, api_vers=api)

    def get_players(self):
        """Returns a dictionary of all players, of format { 'name' : 'id' }. Note that id is a string,
        this is by design, all other functions requiring ID parameters in ScalaMonitor (and indeed, the scala API)
        accept strings.
        """
        return dict((player.name, player.id)
                    for player in self.content_manager.PlayerRS.list())

    def set_player(self, player_id):
        """ Sets the player to be monitored by ScalaMonitor.

        Searches through all players, will find the first player that matches the provided name,
        and set the ScalaMonitor to that player.
        """
        players = self.content_manager.PlayerRS.list()
        try:
            self.player =  next(p for p in players if p.id == player_id)
        except StopIteration as e:
            #re-raise as a more relevant exception
            self.player = None
            raise AttributeError(u'player ' + player_id + u' not found')

        print u'Player set to ' + self.player.name


    def get_player_info(self):
        """Returns a dictionary containing

        {'frame_info : <see get_frame_info()>,
        'playlists' : [<see get_playlists()>],
        'media_on_disk':
        'name' : 'scala_box'
        }
        """
        output = {u'name' : self.player.name, u'id' : self.player.id}

        displays = self.content_manager.PlayerRS.getPlayerDisplays(playerId=self.player.id)

        if not displays: raise ValueError(u'No displays found for player ' + self.player.name)

        #should only ever be one - but better safe than sorry
        for display in displays:
            channels = self.content_manager.ChannelRS.get(channelId=display.channelId)
            if not channels: raise ValueError(u'No channels found for display ' + display.name)

            for channel in channels:
                output[u'frame_info'] = self.get_frame_info(channel)
                playlist_info = {}
                for frame in self.content_manager.ChannelRS.getFrames(channelId=channel.id):
                    #get playlists associated with this frame and add them to dict

                    #we need to do this carefully. we want to make sure the frames list is extended.
                    #Don't care what happens to file infos as these will be the same

                    new_playlists = self.get_playlist_info(channel.id, frame.id)

                    #can't just use playlist_info.update(new_playlists) because that will overwrite/destroy the frames list. do it manually.
                    for pl_name in new_playlists:
                        #if the pl is not present, then add data. Playlist data will always be the same regardless of what
                        #channel/frame id we get it with, the only thing we need to be aware of changing is the frame id
                        if pl_name not in playlist_info:
                            print pl_name, 'adding', frame.id
                            playlist_info[pl_name] = new_playlists[pl_name]
                            playlist_info[pl_name][u'frames'] = [frame.id]
                        #frames must be here, as playlist_info[pl_name] will only exist if we previously did the above if statement
                        elif frame.id not in playlist_info[pl_name][u'frames']:
                            print pl_name, 'appending', frame.id
                            playlist_info[pl_name][u'frames'].append(frame.id)

                output[u'playlists'] = playlist_info

        return output

    def get_frame_info(self, channel):
        """Returns frame info for a channel. Returns a dictionary that looks like the following:
        {'frames': [
            { 'name' : 'screen 1',
              'dimensions' : { 'width' : 1920, 'height': 1080},
              'top_left' : { 'x' : 0, 'y': 0},
              'order' : 0
            },
            ...
            ],
        'id':'1',
        'name':'My Frameset'
        }

        where order is a positive normal number based on where it is in the z-axis. 0 represents the frame at
        the back, with each entry up to n heading towards the front.

        """
        framesets = self.content_manager.ChannelRS.getFrameset(channelId=channel.id)

        if not framesets: raise ValueError('No frameset found for channel ' + channel.name)

        frameset = {u'id' : framesets[0].id, u'name' : framesets[0].name}
        frames = self.content_manager.ChannelRS.getFrames(channelId=channel.id)


        #frame.audioTrack is 'true' if audio, no point logging this as it's automatically included anyway
        frame_info = [ {u'name' : frame.name,
                        u'dimensions' : { u'width': int(frame.width), u'height' : int(frame.height)},
                        u'top_left' : {u'x' : int(frame.x), u'y' : int(frame.y)},
                        u'order' : int(frame.sortOrder)
                       }
                       for frame in frames if frame.audioTrack != 'true']

        frameset['frames'] = frame_info
        return frameset


    def get_media_ids(self, playlistId):
        """Returns a list of all media ids of media contained within a playlist and its sub-playlists
        """
        playlist_items = self.content_manager.PlaylistRS.getPlaylistItems(playlistId=playlistId)
        if not playlist_items: raise ValueError(u'No playlist found with id ' + playlistId)

        out = []
        for item in playlist_items:
            if item.playlistItemType == u'SUB_PLAYLIST':
                #playlist could be full of sub-playlists rather than media items, so recurse through
                out.extend(self.get_media_ids(item.playlistId))
            elif item.playlistItemType == u'MEDIA_ITEM' or item.playlistItemType == u'MESSAGE':
                out.append(item.mediaId)
            else:
                raise ValueError(u'Playlist item ' + item.id + u' has unknown playlist type ' + item.playlistItemType)

        return out

    def get_media_info(self, media):
        """Returns an info dict containing information on a provided MediaTO object
        {'id' : '123',
         'path': '/My Folder/Data',
         'type': 'IMAGE' (see https://developer.scala.com/dev/index.php/MediaTypeEnum)
         'filesize': '1234MB'
        }

        Note, filesize is not guaranteed to be present - it's not contained in message objects
        """

        out = {u'id' : media.id,
                u'path': media.path,
                u'type': media.mediaType
        }
        if media.length:
            out[u'filesize'] = human_filesize(int(media.length))

        return out

    def get_playlist_info(self, channelId, frameId):
        """ Returns an info dict containing information on all playlists contained within this frame
        {'playlist 1' : {
                'items' : {
                    'file 1' : {<see get_media_info()>}
                    'file 2' : {<see get_media_info()>}
                }
            }, ...
        }

        the reason for the nested items dict is that the playlist entry may later contain meta-information
        such as frame information, scheduling information, etc
        """
        output = {}

        #don't ask why channelId needs to be contained within a map - It just does
        timeslots = self.content_manager.ChannelRS.getTimeslots({u'channelId':channelId}, frameId=frameId)
        for t in timeslots:
            if t.playlistId != None:

                media_items = self.get_media_ids(t.playlistId)
                #media_items is a list of media id

                frames = []

                items = {}
                for id in media_items:
                    media = self.content_manager.MediaRS.get(mediaId=id)
                    if not media: raise ValueError(u'Media not found ' + mediaId)

                    items[media[0].name] = self.get_media_info(media[0])

                playlists = self.content_manager.PlaylistRS.get(playlistId=t.playlistId)
                if not playlists: raise ValueError(u'No playlist found with id ' + playlistId)
                output[playlists[0].name] = {}
                output[playlists[0].name][u'items'] = items

        return output

def main():
    #read config file
    try:
        config = json.load(open(os.path.join(os.path.dirname(__file__), u'settings.json'), u'r'))
    except IOError:
        raise IOError(u'The settings.json file does not exist')

    scala = ScalaMonitor(config[u"baseurl"], config[u"authstring"], config[u"api"])
    players = scala.get_players()
    scala.set_player(players[u'Ski Kino 01'])

    s = scala.get_player_info()
    print json.dumps(s)

if __name__ == '__main__':
    main();
