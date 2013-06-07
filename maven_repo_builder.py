#!/usr/bin/env python

"""
maven_repo_builder.py: Fetch artifacts into a location, where a Maven repository is being built given
a list of artifacts and a remote repository URL.
"""

import hashlib
import logging
import optparse
import os
import re
import shutil
import sys
import urlparse

import artifact_list_generator
import maven_repo_util
from maven_artifact import MavenArtifact


def downloadFile(fileUrl, fileLocalPath):
    """Downloads file from the given URL to local path if the path does not exist yet."""
    if os.path.exists(fileLocalPath):
        logging.debug("Artifact already downloaded: " + fileUrl)
    else:
        returnCode = maven_repo_util.download(fileUrl, fileLocalPath)
        if (returnCode == 404):
            logging.warning("Remote file not found: " + fileUrl)


def downloadArtifacts(remoteRepoUrl, localRepoDir, artifact, classifiers):
    """Download artifact from a remote repository along with pom and source jar"""
    artifactLocalDir = localRepoDir + '/' + artifact.getDirPath()
    if not os.path.exists(artifactLocalDir):
        os.makedirs(artifactLocalDir)

    # Download main artifact
    artifactUrl = remoteRepoUrl + '/' + artifact.getArtifactFilepath()
    artifactLocalPath = os.path.join(localRepoDir, artifact.getArtifactFilepath())
    downloadFile(artifactUrl, artifactLocalPath)

    # Download pom
    if artifact.getArtifactFilename() != artifact.getPomFilename():
        artifactPomUrl = remoteRepoUrl + '/' + artifact.getPomFilepath()
        artifactPomLocalPath = os.path.join(localRepoDir, artifact.getPomFilepath())
        downloadFile(artifactPomUrl, artifactPomLocalPath)

    # Download additional classifiers
    if artifact.getArtifactType() != 'pom' and not artifact.getClassifier():
        for classifier in classifiers:
            artifactClassifierUrl = remoteRepoUrl + '/' + artifact.getClassifierFilepath(classifier)
            artifactClassifierLocalPath = os.path.join(localRepoDir, artifact.getClassifierFilepath(classifier))
            downloadFile(artifactClassifierUrl, artifactClassifierLocalPath)


def copyArtifact(remoteRepoPath, localRepoDir, artifact, classifiers):
    """Copy artifact from a repository on the local file system along with pom and source jar"""
    # Download main artifact
    artifactPath = os.path.join(remoteRepoPath, artifact.getArtifactFilepath())
    artifactLocalPath = os.path.join(localRepoDir, artifact.getArtifactFilepath())
    if os.path.exists(artifactPath) and not os.path.exists(artifactLocalPath):
        artifactLocalDir = os.path.join(localRepoDir, artifact.getDirPath())
        if not os.path.exists(artifactLocalDir):
            os.makedirs(artifactLocalDir)
        logging.info('Copying file: ' + artifactPath)
        shutil.copyfile(artifactPath, artifactLocalPath)

    # Download pom
    if artifact.getArtifactFilename() != artifact.getPomFilename():
        artifactPomPath = os.path.join(remoteRepoPath, artifact.getPomFilepath())
        artifactPomLocalPath = os.path.join(localRepoDir, artifact.getPomFilepath())
        if os.path.exists(artifactPomPath) and not os.path.exists(artifactPomLocalPath):
            logging.info('Copying file: ' + artifactPomPath)
            shutil.copyfile(artifactPomPath, artifactPomLocalPath)

    # Download additional classifiers
    if artifact.getArtifactType() != 'pom' and not artifact.getClassifier():
        for classifier in classifiers:
            artifactClassifierPath = os.path.join(remoteRepoPath, artifact.getClassifierFilepath(classifier))
            artifactClassifierLocalPath = os.path.join(localRepoDir, artifact.getClassifierFilepath(classifier))
            if os.path.exists(artifactClassifierPath) and not os.path.exists(artifactClassifierLocalPath):
                logging.info('Copying file: ' + artifactClassifierPath)
                shutil.copyfile(artifactClassifierPath, artifactClassifierLocalPath)


def depListToArtifactList(depList):
    """Convert the maven GAV to a URL relative path"""
    regexComment = re.compile('#.*$')
    #regexLog = re.compile('^\[\w*\]')
    # Match pattern groupId:artifactId:type:[classifier:]version[:scope]
    regexGAV = re.compile('(([\w\-.]+:){3}([\w\-.]+:)?([\d][\w\-.]+))(:[\w]*\S)?')
    artifactList = []
    for nextLine in depList:
        nextLine = regexComment.sub('', nextLine)
        nextLine = nextLine.strip()
        gav = regexGAV.search(nextLine)
        if gav:
            artifactList.append(MavenArtifact.createFromGAV(gav.group(1)))
    return artifactList


def retrieveArtifacts(remoteRepoUrl, localRepoDir, artifactList, classifiers):
    """Create a Maven repository based on a remote repository url and a list of artifacts"""
    if not os.path.exists(localRepoDir):
        os.makedirs(localRepoDir)
    parsedUrl = urlparse.urlparse(remoteRepoUrl)
    protocol = parsedUrl[0]
    repoPath = parsedUrl[2]
    if protocol == 'http' or protocol == 'https':
        for artifact in artifactList:
            downloadArtifacts(remoteRepoUrl, localRepoDir, artifact, classifiers)
    elif protocol == 'file':
        repoPath = remoteRepoUrl.replace('file://', '')
        for artifact in artifactList:
            copyArtifact(repoPath, localRepoDir, artifact, classifiers)
    else:
        logging.error('Unknown protocol: %s', protocol)


def generateChecksums(localRepoDir):
    """Generate checksums for all maven artifacts in a repository"""
    for root, dirs, files in os.walk(localRepoDir):
        for filename in files:
            generateChecksumFiles(os.path.join(root, filename))


def generateChecksumFiles(filepath):
    """Generate md5 and sha1 checksums for a maven repository artifact"""
    if os.path.splitext(filepath)[1] in ('.md5', '.sha1'):
        return
    if not os.path.isfile(filepath):
        return
    for ext, sum_constr in (('.md5', hashlib.md5()), ('.sha1', hashlib.sha1())):
        sumfile = filepath + ext
        if os.path.exists(sumfile):
            continue
        checksum = maven_repo_util.getChecksum(filepath, sum_constr)
        with open(sumfile, 'w') as sumobj:
            sumobj.write(checksum + '\n')


def fetchArtifacts(artifacts, sourceUrl, classifiers, destDir):
    logging.info('Retrieving artifacts from repository: %s', sourceUrl)
    retrieveArtifacts(sourceUrl, destDir, artifacts, classifiers)


def main():
    usage = "Usage: %prog [-c CONFIG] [-a CLASSIFIERS] [-u URL] [-o OUTPUT_DIRECTORY] [FILE...]"
    description = ("Generate a Maven repository based on a file (or files) containing "
                   "a list of artifacts.  Each list file must contain a single artifact "
                   "per line in the format groupId:artifactId:fileType:<classifier>:version "
                   "The example artifact list contains more information. Another usage is "
                   "to provide Artifact List Generator configuration file. There is also "
                   "sample configuration file in examples.")

    cliOptParser = optparse.OptionParser(usage=usage, description=description)
    cliOptParser.add_option('-c', '--config', dest='config',
            help='Configuration file to use for generation of an artifact list for the repository builder')
    cliOptParser.add_option('-u', '--url',
            default='http://repo1.maven.org/maven2/',
            help='URL of the remote repository from which artifacts are downloaded. It is used along with '
                    'artifact list files when no config file is specified.')
    cliOptParser.add_option('-o', '--output',
            default='local-maven-repository',
            help='Local output directory for the new repository')
    cliOptParser.add_option('-a', '--classifiers',
            default='sources',
            help='Comma-separated list of additional classifiers to download')
    cliOptParser.add_option('-l', '--loglevel',
            default='info',
            help='Set the level of log output.  Can be set to debug, info, warning, error, or critical')

    (options, args) = cliOptParser.parse_args()

    # Set the log level
    log_level = options.loglevel.lower()
    if (log_level == 'debug'):
        logging.basicConfig(level=logging.DEBUG)
    elif (log_level == 'info'):
        logging.basicConfig(level=logging.INFO)
    elif (log_level == 'warning'):
        logging.basicConfig(level=logging.WARNING)
    elif (log_level == 'error'):
        logging.basicConfig(level=logging.ERROR)
    elif (log_level == 'critical'):
        logging.basicConfig(level=logging.CRITICAL)
    else:
        logging.basicConfig(level=logging.INFO)
        logging.warning('Unrecognized log level: %s  Log level set to info', options.loglevel)

    if not options.classifiers:
        classifiers = []
    else:
        classifiers = options.classifiers.split(",")

    if options.config is None:
        if len(args) < 1:
            logging.error('Missing required command line argument: path to artifact list file')
            sys.exit(usage)

        # Read the list(s) of dependencies from the specified files
        artifacts = []
        for filename in args:
            if not os.path.isfile(filename):
                logging.warning('Dependency list file does not exist, skipping: %s', filename)
                continue

            logging.info('Reading artifact list from file: %s', filename)
            depListFile = open(filename)
            try:
                dependencyListLines = depListFile.readlines()
                artifacts.extend(depListToArtifactList(dependencyListLines))
            except IOError as e:
                logging.exception('Unable to read file %s: %s', filename, str(e))
                sys.exit()
            finally:
                depListFile.close()

        fetchArtifacts(artifacts, options.url, classifiers, options.output)
    else:
        # generate lists of artifacts from confiuration and the fetch them each list from it's repo
        artifactList = artifact_list_generator.generateArtifactList(options)
        for repoUrl in artifactList.keys():
            artifacts = artifactList[repoUrl]
            fetchArtifacts(artifacts, repoUrl, classifiers, options.output)

    logging.info('Generating checksums...')
    generateChecksums(options.output)
    logging.info('Repository created in directory: %s', options.output)


if  __name__ == '__main__':
    main()
