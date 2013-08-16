import webservices.scws as scws
import json
import os


class ScalaMonitor:
    def __init__(self, baseurl, authstr, api):
        self.content_manager = scws.ConManager(baseurl, authstr, api_vers=api)

    def get_players(self):
        return dict((player.name, player.id)
                    for player in self.content_manager.PlayerRS.list())

    def set_player(self, player_id):
        """ Sets the player to be monitored by ScalaMonitor.

        Searches through all players, will find the first player that matches the provided name.
        """
        players = self.content_manager.PlayerRS.list()
        try:
            self.player =  next(p for p in players if p.id == player_id)
        except StopIteration as e:
            #re-raise as a more relevant exception
            self.player = None
            raise AttributeError(u'player ' + player_id + u' not found')

        print u'Player set to ' + self.player.name


    def get_stored_content(self):

        output = {}

        displays = self.content_manager.PlayerRS.getPlayerDisplays(playerId=self.player.id)

        if not displays: raise ValueError(u'No displays found for player ' + self.player.name)

        #should only ever be one - but better safe than sorry
        for display in displays:
            channels = self.content_manager.ChannelRS.get(channelId=display.channelId)
            if not channels: raise ValueError(u'No channels found for display ' + display.name)

            for channel in channels:
                frameset = self.content_manager.ChannelRS.getFrameset(channelId=channel.id)

                if not frameset: raise ValueError('No frameset found for display ' + display.name)
                frameset = frameset[0]

                output[u'frameset'] = {u'id' : frameset.id, u'name' : frameset.name}

                frames = self.content_manager.ChannelRS.getFrames(channelId=channel.id)

                frame_info = []
                for frame in frames:
                    f = {u'name' : frame.name,
                         u'dimensions' : frame.width + u'x' + frame.height}
                    frame_info.append(f)

                output[u'frames'] = frame_info

        return output



def main():
    #read config file
    try:
        config = json.load(open(os.path.join(os.path.dirname(__file__), u'settings.json'), u'r'))
    except IOError:
        raise IOError(u'The settings.json file does not exist')

    scala = ScalaMonitor(config[u"baseurl"], config[u"authstring"], config[u"api"])
    players = scala.get_players()
    print players
    scala.set_player(players[u'Ski Kino 01'])

    print scala.get_stored_content()

if __name__ == '__main__':
    main();
