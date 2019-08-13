Studio bulk corrections
=======================
The command line script `corrections` allows to perform bulk corrections of 
titles, descriptions, and other attributes for the content nodes of a channel.


Use cases:
  - Bulk modify titles and descriptions (e.g. to fix typos)
  - Translate titles and/or descriptions (for sources with missing structure translations)
  - Enhance content by adding description (case by case detail work done during QA)
  - Add missing metadata like author, copyright holder, and tags to content nodes
  - Perform basic structural edits to channel (remove unwanted topics and content nodes)

Not use cases:
  - Modify a few node attributes (better do manually through the Studio web interface)
  - Structural changes (the corrections workflow does not support node moves)
  - Global changes (if the same modification must be performed on all nodes in the
    channel, it would be better to implement these changes during cheffing)


Credentials
-----------
In order to use the corrections workflow as part of a chef script, you need to
create the file `credentials/studio.json` in the chef repo that contains the
following information:

    {
      "token": "YOURTOKENHERE9139139f3a23232fefefefefefe",
      "username": "your.name@yourdomain.org",
      "password": "yourstudiopassword",
      "studio_url": "https://studio.learningequality.org"
    }

These credentials will be used to make the necessary Studio API calls. Make sure
you have edit rights for this channel.


Corrections workflow
--------------------
The starting point is an existing channel available on Studio, which we will
identify through its Channel ID, denoted `<channel_id>` in code examples below.

### Step 1: Export the channel metadata to CSV
Export the complete metadata of the source channel as a local `.csv` file using:

    corrections export <channel_id>

This will create the file `corrections-export.csv` which can be opened with a
spreadsheet program (e.g. LibreOffice). In order to allow for collaboration,
the content of the spreadsheet must be copied to a shared google sheet with
permissions set to allow external edits.


### Step 2: Edit metadata
In this step the content expert (internal or external) edits the metadata for
each content node in the shared google sheet.
The possible actions (first column) to apply to each row are as follows:
  - `modify`: to apply metadata modifications to the topic or content node
  - `delete`: to remove the topic or content node from the channel
  - Leaving the Action column blank will leave the content node unchanged

All rows with the `modify` keyword in the Action column will undergo metadata
modifications according to the text specified in the `New *` columns of the sheet.

For example, to correct typos in the title and description of a content node you must:
  - Mark the row with Action=`modify` (first column)
  - Add the desired title text in the column `New Title`
  - Add the desired description text in the column `New Description`

Note that not all metadata columns need to be specified. The choice of fields
that will be edited during the `modify` operation will be selected in the next step.


### Step 3: Apply the corrections from a google sheet
Once the google sheet has been edited to contain all desired changes in the
`New *` columns, the next step is apply the corrections:

    corrections apply <channel_id> --gsheet_id='<gsheet_id>' --gid=<gsheet_gid>

where `<gsheet_id>` is the google sheets document identifier (take from the URL)
and `<gsheet_gid>` is identifier of the particular sheet within the spreadsheet
document that contains the corrections (usually `<gsheet_gid>=0`).

The attributes that will be edited during the `modify` operation is specified
using the `--modifyattrs` command line argument. For example to apply modifications
only to the `title` and `description` attributes use the following command: 

    corrections apply <channel_id> --gsheet_id='<gsheet_id>' --gid=<gsheet_gid> --modifyattrs='title,description'

Using the above command will apply only the modifications only from the
`New Title` and `New Description` columns and ignore modifications to copyright holder,
author, and tags attributes.
The default settings is `--modifyattrs=title,description,author,copyright_holder`.


Status
------
Note the corrections workflows is considered "experimental" and to be used only
when no other options are viable (too many edits to do manually through the Studio
web interface).
