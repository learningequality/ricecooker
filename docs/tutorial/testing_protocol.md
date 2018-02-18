New content type: ePub
======================


PR ordering:
  - merge le-utils PR first
  - release as le-utils 0.2
  - update studio/kolibri/ricecooker
  - deploy Studio
    - backward compatibility policy: must not import content channels containing ePubsupport
      on any installation older than 0.7.3 (or whenever conservative content-type import implemented)
    - WHY? Otherwise people might download content they can't render—it's not a
      scenario that will crash Kolibri, but want to avoid unnecessary downloads.
  - release ricecooker
  - plan release for Kolibri 0.9/0.10/0.11?




Studio
------

### Code

    git clone https://github.com/ivanistheone/content-curation
    cd content-curation
    git checkout feature/ePubsupport


### Install

    virtualenv -p python2.7 venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install -r requirements_dev.txt
    pip install -U git+https://github.com/ivanistheone/le-utils@feature/ePubsupport
    npm install


Need two other tabs start the necessary services:

    # Start DB
    pg_ctl -D /usr/local/var/postgresql@9.6 start
    # Start Redis
    redis-server /usr/local/etc/redis.conf



If starting without previous Studio installation, you'll need to create DB and
run the steps from Studio README: https://github.com/fle-internal/content-curation

    createdb contentcuration
    psql
        CREATE USER learningequality with NOSUPERUSER INHERIT NOCREATEROLE CREATEDB LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'kolibri';
        CREATE DATABASE "contentcuration" WITH TEMPLATE = template0 OWNER = "learningequality";

    cd contentcuration
    python manage.py makemigrations
    python manage.py migrate --settings=contentcuration.dev_settings
    python manage.py loadconstants --settings=contentcuration.dev_settings
    python manage.py calculateresources --settings=contentcuration.dev_settings --init
    python manage.py collectstatic --noinput --settings=contentcuration.dev_settings
    python manage.py collectstatic_js_reverse --settings=contentcuration.dev_settings


If you have an existing Studio installation just need to run these:

    python manage.py loadconstants --settings=contentcuration.dev_settings
    
        ***** Loading Constants *****
        Site: 3 constants saved (0 new)
        License: 9 constants saved (0 new)
        FileFormat: 14 constants saved (1 new)
        ContentKind: 6 constants saved (0 new)
        FormatPreset: 17 constants saved (1 new)
        Language: 228 constants saved (0 new)
        ************ DONE. ************


For test instrucrions to run need to load the admin user fixture token.
If you already have an admin user in your DB, you can skip this step, otherwise
you admin user (the user with user id = 1) will get overwritten to a user with
login `content@learningequality.org` and password `admin123`:

    python manage.py \
      loaddata contentcuration/contentcuration/fixtures/admin_user.json \
      --settings=contentcuration.dev_settings

Now we can load the admin user token `26a51f88ae50f4562c075f8031316eff34c58eb8`:

    python manage.py \
      loaddata contentcuration/contentcuration/fixtures/admin_user_token.json \
      --settings=contentcuration.dev_settings


### Run

    python manage.py runserver --settings=contentcuration.dev_settings


You should be able to login at http://127.0.0.1:8000 using `content@learningequality.org:admin123`.




Ricecooker
----------


### Code


    git clone https://github.com/ivanistheone/ricecooker.git
    cd ricecooker
    git checkout feature/ePubsupport
    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -e .
    

### Run ePub test chef

    cd docs/tutorial/

    # expected files to be present:
    # samplefiles/
    # └── documents
    #     └── laozi_tao-te-ching.epub
    
    # IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT 
    # IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT 
    # IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT 
    # IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT 
    #
    # DO NOT CONTINUE WITHOUT SETTING THIS ENV VARIABLE
    export CONTENTWORKSHOP_URL="http://127.0.0.1:8000"
    # set -x CONTENTWORKSHOP_URL "http://127.0.0.1:8000"
    #
    # IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT 
    # IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT 
    # IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT IMPORTANT 
    #
    ./epubchef.py -v --reset --token='26a51f88ae50f4562c075f8031316eff34c58eb8'



Should run w/o errors and produce this link at the end of the run:
http://127.0.0.1:8000/channels/982afe31f3af57b6a5acf21b4ae5bed8/edit


### Studio steps:
  - Publish the channel big [PUBLISH] button at top right
  - Make the channel public using the rightmost button on http://127.0.0.1:8000/channels/administration/
    We global now! Let's go import in Kolibri.



Kolibri
-------

### Code
    
    git clone https://github.com/learningequality/kolibri.git
    cd kolibri
    git checkout feature/ePubsupport
    # this branch contains main changes from pull/3197=epub_me_good + some minor fixes



### Backend

    virtualenv -p python2.7 venv
    source vevn/bin/activate
    pip install -r requirements/dev.txt
    pip install -e .
    pip install -U git+https://github.com/ivanistheone/le-utils@feature/ePubsupport


### Frontend

    yarn install

    # May need to edit package.json if using newer node.js:  s/"6.x"/">= 6.x"/
    # npm rebuild node-sass --python=/usr/bin/python2.7  # partial fix when using py3, but better not use py3... bcs node-gyp is being a difficult

    kolibri plugin kolibri.plugins.document_epub_render enable
    yarn install  # to install document_epub_render dependencies


### Run devserver

    set -x CENTRAL_CONTENT_DOWNLOAD_BASE_URL "http://127.0.0.1:8000"
    yarn run devserver 'localhost:8080'


### Kolibri steps:
  - Setup facility
  - login as a device owner
  - import channel
  - check the book at: http://localhost:8080/learn/#/topics/c/589553ceb7115e4f8a95daaaa1b8d11f


