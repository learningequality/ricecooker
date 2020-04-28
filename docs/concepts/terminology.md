Terminology
===========

This page lists key concepts and technical terminology used as part of the
content integration work within Learning Equality.


Content Pipeline
----------------
The combination of software tools and procedures used to convert content
from an external content source to becoming a Kolibri Channel available
for use in the Kolibri Learning Platform. The Kolibri Content Pipeline is
a collaborative effort between educational experts and software developers.



Channel Spec
------------
A content specification document, or Channel Spec, is a blueprint document
that specifies the structure of the Kolibri channel that is to be created.

Channel Specs are an important aspect of the content integration process for two reasons:

1. It specifies what needs to be done.
   The channel spec establishes an agreement between the curriculum specialist
   and the developer who will be writing the content integration script.

2. It serves to define when the work is done.
   Used as part of the [review process](reviewing_channels.md) to know when the
   channel is "Spec Compliant," i.e. the channel structure in Kolibri matches the blueprint.

A Channel Spec document includes the following information:

 - Channel Title: usually of the form `{Source Name} ({lang})` where `{Source Name}`
   is chosen to be short and descriptive, and `{lang}` is included in the title
   to make it easy to search for content in this language.
 - Channel Description: a description (up to 400 characters) of the channel and its contents.
 - Languages: notes about content language, and special handling for multilingual content, subtitles, or missing translations
 - Files Types: info about what content kinds and file types to look for
 - Channel Structure: a specification of the desired topic structure for the channel.
   This is the key element in the Channel Spec and often requires domain expertise
   to take into account the needs of the teachers and learners who will be accessing this content.
 - Links and sample content
 - Credentials: info about how to access the content (e.g. info about API access)
 - Technical notes: The Channel Spec can include guidance about technical aspects
   like content transformations (for example, the need to compress the videos so that they take up less space).

For more info about each of these aspects, see the section "Creating a Content Channel Spec"
in the [Kolibri Content Integration Guide](https://learningequality.org/r/integration-guide).


Content Integration Script (aka SushiChef)
------------------------------------------
The content integration scripts that use the `ricecooker` library to
generate Kolibri Channels are commonly referred to as **SushiChef**
scripts. The responsibility of a `SushiChef` script is to download the source
content, perform any necessary format or structure conversions to create
a content tree viewable in Kolibri, then to upload the output of this
process to Kolibri Studio for review and publishing.

Conceptually, `SushiChef` scripts are very similar to web scrapers,
but with specialized functions for optimizing the content for Kolibri's
data structures and capabilities.

