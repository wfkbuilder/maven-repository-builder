#!/usr/bin/env python

import logging
import optparse

import maven_repo_util
from configuration import Configuration
from artifact_list_builder import ArtifactListBuilder
from filter import Filter
from maven_artifact import MavenArtifact


def _generateArtifactList(options):
    # load configuration
    logging.info("Loading configuration...")
    config = Configuration()
    config.load(options)

    # build list
    logging.info("Building artifact list...")
    listBuilder = ArtifactListBuilder(config)
    artifactList = listBuilder.buildList()

    logging.debug("Generated list contents:")
    for gat in artifactList:
        priorityList = artifactList[gat]
        for priority in priorityList:
            versionList = priorityList[priority]
            for version in versionList:
                artSpec = versionList[version]
                for classifier in artSpec.classifiers:
                    if classifier == "":
                        logging.debug("  %s:%s", gat, version)
                    else:
                        logging.debug("  %s:%s:%s", gat, classifier, version)

    #filter list
    logging.info("Filtering artifact list...")
    listFilter = Filter(config)
    artifactList = listFilter.filter(artifactList)

    logging.debug("Filtered list contents:")
    for gat in artifactList:
        priorityList = artifactList[gat]
        for priority in priorityList:
            versionList = priorityList[priority]
            for version in versionList:
                artSpec = versionList[version]
                for classifier in artSpec.classifiers:
                    if classifier == "":
                        logging.debug("  %s:%s", gat, version)
                    else:
                        logging.debug("  %s:%s:%s", gat, classifier, version)

    logging.info("Artifact list generation done")
    return artifactList


def generateArtifactList(options):
    """
    Generates artifact "list" from sources defined in the given configuration in options. The result
    is dictionary with following structure:

    <repo url> (string)
      L artifacts (list of MavenArtifact)
    """

    options.allclassifiers = (options.classifiers == '__all__')

    artifactList = _generateArtifactList(options)
    #build sane structure - url to MavenArtifact list
    urlToMAList = {}
    for gat in artifactList:
        priorityList = artifactList[gat]
        for priority in priorityList:
            versionList = priorityList[priority]
            for version in versionList:
                artSpec = versionList[version]
                url = artSpec.url
                for classifier in artSpec.classifiers:
                    if classifier == "" or options.allclassifiers:
                        artifact = MavenArtifact.createFromGAV(gat + ((":" + classifier) if classifier else "") +
                                                               ":" + version)
                        urlToMAList.setdefault(url, []).append(artifact)
    return urlToMAList


def main():
    description = "Generate artifact list from sources defined in the given congiguration file"
    cliOptParser = optparse.OptionParser(usage="Usage: %prog -c CONFIG", description=description)
    cliOptParser.add_option(
        '-c', '--config', dest='config',
        help='Configuration file to use for generation of an artifact list for the repository builder'
    )
    cliOptParser.add_option(
        '-a', '--allclassifiers', default=False, action='store_true',
        help='Find all available classifiers'
    )
    cliOptParser.add_option(
        '-l', '--loglevel',
        default='info',
        help='Set the level of log output.  Can be set to debug, info, warning, error, or critical'
    )
    cliOptParser.add_option(
        '-L', '--logfile',
        help='Set the file in which the log output should be written.'
    )
    (options, args) = cliOptParser.parse_args()

    # Set the log level
    maven_repo_util.setLogLevel(options.loglevel, options.logfile)

    artifactList = _generateArtifactList(options)

    maven_repo_util.printArtifactList(artifactList, options.allclassifiers)


if __name__ == '__main__':
    main()
