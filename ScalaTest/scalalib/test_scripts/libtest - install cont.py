import scalalib
import sys

svars = scalalib.sharedvars()

if __name__ == '__main__':

    log = scalalib.get_logger(scala=0, con=1)
    scalalib.install_content(
        "C:\Documents and Settings\mgmiller\Desktop\dvd keyboard aerobed.txt", 
        autostart=True)
else:

    scalalib.install_content(svars.file_to_install, autostart=False)


