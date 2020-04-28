Developer workflows
===================



## The Kolibri UPLOADCHANNEL-PUBLISH-IMPORT content workflow

Running a sushichef script is only one of the steps in a channel's journey within
the Kolibri platform. Here is the full picture:

```
                  Sushichef script          Kolibri Studio        Kolibri demo server
    SPEC----->----UPLOADCHANNEL----->-------DEPLOY+PUBLISH---->---IMPORT+REVIEW
     \  \         /                                                       /
      \  `clarif.´                                                       /
       \                                                                /
        `---------------- spec compliance checks ----------------------´
```

It is the responsibility of the chef author to take a content channel all the way
through this workflow and make sure that the final channel works in Kolibri.

Notes on specific steps:
  - `SPEC`: the **channel spec** describes the target channel structure, licensing,
    and technical notes about content transformations that might be necessary.
    All this information will be available on the notion card for this source.
  - `UPLOADCHANNEL`: the main task of the chef author is to implement all the extraction
    and content transformation described in the spec. If anything in the spec is
    missing or requires further clarification, post comments on the Notion card.
    If you run into any kind of difficulties during the cheffing process, post a
    question in the LE slack channel `#sushi-chefs` and someone from the content
    team will be able to assist you. For example, "Hello @here I'm having trouble
    with the {{cookiecutter.channel_name}} chef because X and Y cannot be organized
    according to the spec because Z."
  - `DEPLOY` and `PUBLISH`: once the channel is uploaded to Kolibri Studio you
    can preview the structure and update the information on the notion card.
    Use the `DEPLOY` button to take the channel out of "draft mode" (staging).
    The next step is to export the channel in the format necessary for use in
    Kolibri using the `PUBLISH` button on Studio. The PUBLISH action exports
    all the channel metadata to a sqlite3 DB file
    `https://studio.learningequality.org/content/databases/{channel_id}.sqlite3`
    the first time a channel is PUBLISH-ed a secret token is generated that can
    be used to import the channel in Kolibri.
  - `IMPORT`: the next step is to import your channel into a Kolibri instance. You
    can use Kolibri installed on your local machine or an online demo server.
    Admin (`devowner` user) credentials for the demo server will be provided for you
    so that you can import and update the channel every time you push a new version.
    Follow these steps to import your channel `Device` > `IMPORT` > `KOLIBRI STUDIO (online)` >
    `Try adding a token`, add the channel token, select all nodes > `IMPORT`.
  - `REVIEW`: You can now go to the Kolibri Learn tab and preview your channel to
    see it the way learners will see it. Take the time to click around and browse
    the content to make sure everything works as expected. Update the notion card
    and leave a comment. For example "First draft of channel uploaded to demo server."
    This would be a good time to ask a member of the LE content team to review
    the channel. You can do this using the `@Person Name` in your notion comment.
    Consult the content source notion card to know who the relevant people to tag.
    For example, you can @-comment the `Library` person on the card to ask them
    to review the channel—be sure to specify the channel's "level of readiness"
    in your comment, e.g., if it's a draft version for initial feedback, or
    the near-final, spec-compliant version ready for detailed review and QA.
    For async technical questions tag the `SushOps` person on the card or post
    your question in the `#sushi-chefs` channel. For example, "I downloaded this
    html and js content, but it doesn't render right in Kolibri because of the
    iframe sandboxing." or "Does anyone have sample code for extracting content
    X from a shared drive link Y of type Z?".









## The Kolibri UPLOADCHANNEL-PUBLISH-UPDATE content workflow

The process is similar to the initial upload and import, but some steps are
different because a version of the channel is already available:
  - `UPLOADCHANNEL`: to upload a new version of a content channel, simply re-run the chef
    script. The newly uploaded channel tree will replace the old tree on Studio
    (assuming the `source_domain` and `source_id` of the channel haven't changed).
    - The new version of the channel will be uploaded to a "staging tree" instead
      of replacing the current tree, which will allow you to preview the changes
      to the channel on Studio before replacing the existing tree. Use the `DEPLOY`
      button on Studio to complete the upload and replace the current tree.
    - By default, ricecooker will cache all files that have been previously uploaded
      to Studio in order to avoid the need to download and compress files each
      time the chef runs. You can pass the `--update` command line argument to
      the chef script to bypass this caching mechanism. This is useful when
      the source files have changed, but their URLs and filenames haven't changed.
  - `DEPLOY` and `PUBLISH`: every time you upload a new content to your channel,
    you must repeat the deploy and publish step on Studio to regenerate the sqlite3
    DB file that is used for importing into Kolibri. At the end of the PUBLISH process,
    the channel version number will increase by one. The channel token stays the same.
  - `UPDATE`: the process of updating a channel in Kolibri is similar to the
    `IMPORT` step described above, but the actions are different because a version
    of the channel is already available. Go to the `Device` > `Channels` page in
    Kolibri and use the `OPTIONS` button next to your channel, select `Import more` >
    `KOLIBRI STUDIO (online)` > `UPDATE`, select all nodes then click `IMPORT`.
    Updating a channel takes much less time than the initial import because Kolibri
    only needs to import the new files that have been added to the channel.
    Once the update process is complete, you can notify the relevant members of
    the LE content team to let them know a new version is available for review.










## Rubric
Use the following rubric as a checklist to know when a sushi chef script is done:

### Main checks
1. Does the channel correspond to the spec provided?
2. Does the content render as expected when viewed in Kolibri?

### Logistic checks
1. Is the channel uploaded to Studio and `PUBLISH`-ed?
2. Is the channel imported to a demo server where it can be previewed?
3. Is the information about the channel token, the studio URL, and demo server URL
   on the notion card up to date? See the [Studio Channels table](https://www.notion.so/761249f8782c48289780d6693431d900).
   If a card for your channel doesn't exist yet, you can create one using the
   `[+ New]` button at the bottom of the table.

### Metadata checks
1. Do all nodes have appropriate titles?
2. Do all nodes have appropriate descriptions (when available in the source)?
3. Is the correct [language code](https://github.com/learningequality/le-utils/blob/master/le_utils/resources/languagelookup.json)
   set on all nodes and files?
4. Is the `license` field set to the correct value for all nodes?
5. Is the `source_id` field set consistently for all content nodes?
   Try to use unique identifiers based on the source website or permanent url paths.
