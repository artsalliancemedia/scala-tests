## Scala tests

#### Scala Tools
Creates a new playlist in Scala consisting of an item "test_image.png", puts the playlist into a schedule and updates the player to sync the new changes.

#### Scala Monitor
Provides a class to monitor a chosen player, and report back a variety of information on that player such as files it uses and screen layouts.

### Installation

Python 2.6.x is required
Just clone the repo, all requirements are included (see below)

### Next Steps

Take a copy of *settings-template.json*, name it *settings.json* and fill out the fields.

By default, the application will use this *settings.json* file.

To start the scala test app run:
*python scala_tools.py*

To start the monitoring app run:
*python scala_monitor.py*

### Included libraries

This includes the following libraries from Scala. They are not provided via pip that is why they are directly in the repo.

### Scalalib

A set of modules with tools and utilities for common needs at playback
time, communication, synchronization, publishing, Player provisioning, etc.


#### Scws

Webservice modules for communicating with Content Manager 5 in a simple
manner.  Example command-line upload to CM included.


### Creating your own python code for interacting with Scala

#### Initial steps

The easiest way to start is to grab the webservices subfolder of this repository. scws is not available on `pip` or `easy_install`, so just leave it as a subfolder of your directory.

    from webservices.scws import scws

    baseurl = "http://my-scala-box:8080/ContentManager/"
    authstr = "username:password"
    api = "v1.2"
    content_manager = scws.ConManager(baseurl, authstr, api_vers=api)

#### Simple use cases

Now the Content Manager is connected, you can usue the *content_manager* object to access a variety of functions. For example, to list the names of all players:

    players = content_manager.PlayerRS.list()
    for player in players:
        print player.name

The Content Manager API can be found at [the Scala developer wiki](https://developer.scala.com/dev/index.php/API_version_main), although take care not to
try to call functions from version 1.3.

The API calls typically take in an ID of an object to find, and typically return an array of relevant objects. More complex search functions can often take a SearchCritera object.
For example, to search for all channels with names containing "test":

    channel_filter = scws.TObj()
    channel_filter.column       = u'name'
    channel_filter.restriction  = u'LIKE'
    channel_filter.value        = u'%test%'
    test_channels = content_manager.ChannelRS.list(searchCriteria=channel_filter)

A quick tutorial is available [here](https://developer.scala.com/dev/index.php/WebServicesTutorial_python_mike).

#### Class Layout
The basic structure of a Scala player is as follows. The Content Manager will have links to a variety of *Player*s. A *Player* contains a number of *Display*s, which each contains a single *Channel*. A *Channel* has a list of *Timeslot*s and a *Frameset*. The *Frameset* contains multiple *Frame*s, and dictates how the frames are laid out, any bezel sizes, the ordering of frames from front to back, and so on. The *Schedule* dictates at what times a *Playlist* is shown, and on which *Frame*s. A *Playlist* can contain *Media*, *Audio*, or *Data*, and specifies ordering, transitions, lengths images are displayed for, and so on and so forth.

                                /-> Timeslot -> Playlist -> Media
    Player -> Display -> Channel
                                \-> Frameset -> Frame

#### MetaValues
Players, Messages and Media items can contain meta-values, which are accessed differently to the main objects, using *MediaRS.getMetaValues(mediaId=id)* for example.


### Some thoughts on the Scala API

The Scala API is perfectly functional, and relatively full featured. While somewhat confusing to use and not hugely "pythonic", it does do its job reasonably thoroughly and effictively. A bit of care has to be taken with a few quirks of it though. For example I could not get it to return transmission or data size from `PlanGeneratorRS.getPlanStatus()`. For some bizarre reason `ChannelRS.getTimeslots(channelId, frameId)` does not work, instead you must call `ChannelRS.getTimeslots({'channelId':channel}, frameId=frame)` instead.

It does not appear possible to in any way easily directly interact with a Scala Player, instead, all interaction should be done through the Content Manager. There is a scripting language called [ScalaScript](https://developer.scala.com/dev/index.php/ScalaScript_Language) that may potentially be used to interact with the player directly.
