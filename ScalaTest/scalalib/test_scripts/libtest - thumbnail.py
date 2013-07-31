import sys, time
sys.path.append('.'); sys.path.append('..')
from glob import glob
import scalalib as sl
sl.get_logger(level='debug')

from scalalib import thumbnail_gen

thumbnail_gen(
    r'C:\Documents and Settings\training\Desktop\scalalib\libtest.sca', 
    'c:\\thbn.jpg', 96, 96, options='k',
    tmpl_CityName='Kathmandu', tmpl_Greeting='d:\\Namaste.jpg' )
