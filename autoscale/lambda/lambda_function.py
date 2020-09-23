import json
import time
from botocore.vendored import requests
from botocore.vendored.requests.exceptions import HTTPError

ControlHubUrl = "https://cloud.streamsets.com"
ControlHubOrg = "myorg.com"
ControlHubUser = "serviceAccount@myorg.com"
ControlHubPassword = ""


def lambda_handler(event, context):
    error = None
    response = None

    if 'action' in event:
        if event['action'] in ['pre-start', 'post-start', 'pre-stop']:
            (error, sessionToken) = get_session_token(ControlHubUrl, ControlHubUser, ControlHubPassword)
            if error:
                return {'error': error, 'response': str(sessionToken)}

        if event['action'] == 'pre-start':
            (error, response) = pre_start(sessionToken, ControlHubUrl, ControlHubOrg)
        elif event['action'] == 'post-start':
            if 'sdcId' in event and 'labels' in event and 'groups' in event:
                (error, response) = post_start(sessionToken, ControlHubUrl, ControlHubOrg, ControlHubUser,
                                               event['sdcId'], event['labels'], event['groups'])
            else:
                error = "post-start action missing sdcId, labels, or groups"
        elif event['action'] == 'pre-stop':
            if 'sdcId' in event:
                (error, response) = pre_stop(sessionToken, ControlHubUrl, ControlHubOrg, event['sdcId'])
            else:
                error = "pre-stop action missing sdcId"
        else:
            error = "Action not implemented."
    else:
        error = "Action missing in request."

    if error:
        return {'error': error}
    else:
        return {'response': response}


def get_session_token(host, user, password):
    url = "{}/security/public-rest/v1/authentication/login".format(host)
    headers = {'Content-Type': 'application/json', 'X-Requested-By': 'SDC'}
    data = {
                "userName": user,
                "password": password
           }

    try:
        r = requests.post(url, headers=headers, data=json.dumps(data))
        r.raise_for_status()
        return (None, r.cookies["SS-SSO-LOGIN"])
    except HTTPError as http_err:
        return (str(http_err), r)
    except Exception as err:
        return (str(err), r)


def pre_start(sessionToken, host, org):
    url = "{}/security/rest/v1/organization/{}/components".format(host, org)
    data = {
                'organization': org,
                'componentType': 'dc',
                'numberOfComponents': 1,
                'active': True
            }

    (error, response) = sch_request('PUT', url, sessionToken, data)
    if error:
        return (error, response)

    return (None, response[0]['fullAuthToken'])


def post_start(sessionToken, host, org, user, sdcId, labels, groups):
    # Set ACLs on the SDC
    url = "{}/jobrunner/rest/v1/sdc/{}/acl".format(host, sdcId)
    data = {
                'resourceId': sdcId,
                'organization': org,
                'permissions': [
                    {
                        'subjectId': groups,
                        'subjectType': 'GROUP',
                        'actions': ['READ', 'WRITE', 'EXECUTE']
                    },
                    {
                        'subjectId': user,
                        'subjectType': 'USER',
                        'actions': ['READ', 'WRITE', 'EXECUTE']
                    }
                ]
            }
    (error, response) = sch_request('POST', url, sessionToken, data)
    if error:
        return (error, response)

    # Set Labels on the SDC
    labels = labels.split(',')
    url = "{}/jobrunner/rest/v1/sdc/{}/updateLabels".format(host, sdcId)
    data = {
                'id': sdcId,
                'organization': org,
                'labels': labels
           }
    (error, response) = sch_request('POST', url, sessionToken, data)
    if error:
        return (error, response)

    # Get all of the jobs matching the configured labels
    jobIds = []
    for label in labels:
        url = "{}/jobrunner/rest/v1/jobs?organization={}&jobLabel={}".format(host, org, label)
        (error, response) = sch_request('GET', url, sessionToken)
        if error:
            return (error, response)

        for job in response:
            jobIds.append(job['id'])

    # Balance the jobs
    url = "{}/jobrunner/rest/v1/jobs/balanceJobs".format(host)
    (error, response) = sch_request('POST', url, sessionToken, jobIds)
    if error:
        return (error, response)

    return (error, "Success")


def pre_stop(sessionToken, host, org, sdcId):
    # Get the jobs running on the SDC
    (error, jobIds) = get_jobs_by_sdcId(sessionToken, host, sdcId)
    if error:
        return (error, None)

    # Remove all labels from the SDC
    url = "{}/jobrunner/rest/v1/sdc/{}/updateLabels".format(host, sdcId)
    data = {
                'id': sdcId,
                'organization': org,
                'labels': []
           }
    (error, response) = sch_request('POST', url, sessionToken, data)
    if error:
        return (error, response)

    # Sync the jobs
    url = "{}/jobrunner/rest/v1/jobs/syncJobs".format(host)
    (error, response) = sch_request('POST', url, sessionToken, jobIds)
    if error:
        return (error, response)

    # Wait until there are no jobs running
    while True:
        (error, jobIds) = get_jobs_by_sdcId(sessionToken, host, sdcId)
        if error is not None:
            return (error, None)
        if len(jobIds) == 0:
            break
        time.sleep(5)

    # Deactivate the SDC's token
    url = "{}/security/rest/v1/organization/{}/components/deactivate".format(host, org)
    (error, response) = sch_request('POST', url, sessionToken, [sdcId])
    if error:
        return (error, response)

    # Delete the SDC's token
    url = "{}/security/rest/v1/organization/{}/components/delete".format(host, org)
    (error, response) = sch_request('POST', url, sessionToken, [sdcId])
    if error:
        return (error, response)

    # Delete the SDC
    url = "{}/jobrunner/rest/v1/sdc/{}".format(host, sdcId)
    (error, response) = sch_request('DELETE', url, sessionToken)
    if error:
        return (error, response)

    return (None, "Success")


def get_jobs_by_sdcId(sessionToken, host, sdcId):
    jobIds = []

    url = "{}/jobrunner/rest/v1/sdc/{}/pipelines".format(host, sdcId)
    (error, response) = sch_request('GET', url, sessionToken)
    if error:
        return (error, response)

    if response:
        for job in response:
            if job['localPipeline'] is False:
                jobIds.append(job['jobId'])

    return (None, jobIds)


def sch_request(method, url, sessionToken, data=None):
    headers = {'Content-Type': 'application/json', 'X-Requested-By': 'SDC', 'X-SS-User-Auth-Token': sessionToken}

    try:
        r = requests.request(method, url, headers=headers, data=json.dumps(data))
        r.raise_for_status()
        if r.content:
            return (None, json.loads(r.content))
        else:
            return (None, None)
    except HTTPError as http_err:
        return (str(http_err), r)
    except Exception as err:
        return (str(err), r)
