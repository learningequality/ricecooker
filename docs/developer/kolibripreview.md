Debugging HTML5 app rendering in Kolibri
========================================


The problem
-----------
The edit-preview loop for HTML5App nodes is very time consuming since it requires
running the sushichef script, waiting for the channel to publish in Studio, then
going through the channel UPDATE steps in Kolibri before you can see the edits.


Local HTMLZip replacement hack
------------------------------
It is possible to have a quick edit-refresh-debug loop for HTML5Apps using a local
Kolibri instance by zipping and putting the work-in-progress `webroot/` content
into an existing zip file in the local `.kolibrihome/content/storage/` directory.

Under normal operations files in `content/storage/` are stored based on md5 hash
of their contents, but if you replace a file with a different contents, Kolibri
will still load it.

We provide the script [kolibripreview.py](https://github.com/learningequality/ricecooker/blob/master/ricecooker/utils/kolibripreview.py)
to help with this file-replacement process used for HTML5App debugging and dev.



Prerequisites
-------------

1. [Install](https://kolibri.readthedocs.io/en/latest/install/index.html) Kolibri on your machine.
2. Find the location of `KOLIBRI_HOME` directory for your Kolibri instance.
   By default Kolibri will use the directory `.kolibri` in your User's home folder.
3. [Import](https://kolibri.readthedocs.io/en/latest/manage/resources.html#import-with-token)
   the **HTML5App Dev Channel** using the token `bilol-vivol` into Kolibri.
   Note you can use any channel that contains .zip files for this purpose, but
   the code examples below are given based on this channel, which contains the
   placeholder file `9cf3a3ab65e771abfebfc67c95a8ce2a.zip` which we'll be replacing.
   After this step, you can check the file `$KOLIBRI_HOME/content/storage/9/c/9cf3a3ab65e771abfebfc67c95a8ce2a.zip`
   exists on your computer and view it at
   [http://localhost:8080/en/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52](http://localhost:8080/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52)
4. Download the helper script `kolibripreview.py` and make it executable:
   ```bash
   wget https://raw.githubusercontent.com/learningequality/ricecooker/master/ricecooker/utils/kolibripreview.py
   chmod +x kolibripreview.py   
   ```


Usage
-----
Assuming you have prepared work-in-progress draft directory `webroot`, you can
load int into Kolibri by running:

```bash
./kolibripreview.py --srcdir webroot --destzip ~/.kolibri/content/storage/9/c/9cf3a3ab65e771abfebfc67c95a8ce2a.zip
```
The script will check that the file `webroot/index.html` exists then create a zip
file from the `webroot` directory and replace the placeholder .zip file.
Opening and refreshing the page
[http://localhost:8080/en/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52](http://localhost:8080/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52)
will show you to the result of your work-in-progress `HTML5App`.

You'll need to re-run the script whenever you make changes to the `webroot` then
refresh the [Kolibri page](http://localhost:8080/en/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52).
It's not quite webpack live dev server, but much faster than going through the
ricecooker uploadchannel > Studio PUBLISH > Kolibri UPDATE, Kolibri IMPORT steps.




Testing in different releases
-----------------------------
If you need to test your `HTML5App` works in a specific version of Kolibri, you
can quickly download the `.pex` file and run it as a "one off" test in temporary
`KOLIBRI_HOME` location (to avoid clobbering your main Kolibri install).
A `.pex` file is a self-contained Python EXecutable file that contains all libraries
and is easy to run without requiring setting up a virtual environment or installing
dependencies. You can download Kolibri `.pex` files from the [Kolibri releases page on github](https://github.com/learningequality/kolibri/releases).

The instructions below use the pex file `kolibri-0.13.2.pex` which is the latest
at the time of writing this, but you can easily adjust the commands to any version.

```bash
# Download the .pex file
wget https://github.com/learningequality/kolibri/releases/download/v0.13.2/kolibri-0.13.2.pex

# Create a temporary directory
mkdir -p ~/.kolibrihomes/kolibripreview
export KOLIBRI_HOME=~/.kolibrihomes/kolibripreview

# Setup Kolibri so you don't have to go through the setup wizard
python kolibri-0.13.2.pex manage provisiondevice \
  --facility "$USER's Kolibri Facility" \
  --preset informal \
  --superusername devowner \
  --superuserpassword admin123 \
  --language_id en \
  --verbosity 0 \
  --noinput

# Import the HTML5App Dev Channel
python kolibri-0.13.2.pex manage importchannel network 0413dd5173014d33b5a98a8c00943724
python kolibri-0.13.2.pex manage importcontent network 0413dd5173014d33b5a98a8c00943724

# Start Kolibri (and leave it running)
python kolibri-0.13.2.pex start --foreground
```

After that you can use the script as usual: 

1. Replace placeholder .zip with contents of `webroot`:
   ```bash
   ./kolibripreview.py  --srcdir webroot --destzip=~/.kolibrihomes/kolibripreview/content/storage/9/c/9cf3a3ab65e771abfebfc67c95a8ce2a.zip
   ```
2. Open and refresh [http://localhost:8080/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52](http://localhost:8080/learn/#/topics/c/60fe072490394595a9d77d054f7e3b52)



Further reading
---------------
See the docs page on [HTML Apps](../htmlapps.md) for info about technical details
and best practices for packaging web content for use in the Kolibri Learning Platform.
