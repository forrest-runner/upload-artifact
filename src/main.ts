import { relative } from 'node:path'
import { open, rm, writeFile } from 'node:fs/promises'

import * as core from '@actions/core'
import { HttpClient } from '@actions/http-client'
import { findFilesToUpload } from './search'

const FORREST_HOST = 'http://10.0.2.4'

export interface UploadInputs {
  artifactName: string
  searchPath: string
  includeHiddenFiles: boolean
  authToken: string
}

export function getInputs(): UploadInputs {
  const name = core.getInput('name') || 'artifact'
  const path = core.getInput('path', { required: true })
  const includeHiddenFiles = core.getBooleanInput('include-hidden-files')
  const authToken = core.getInput('token')

  return {
    artifactName: name,
    searchPath: path,
    includeHiddenFiles: includeHiddenFiles,
    authToken: authToken
  }
}

export async function run(): Promise<void> {
  const inputs = getInputs()
  const searchResult = await findFilesToUpload(
    inputs.searchPath,
    inputs.includeHiddenFiles
  )

  let headers = undefined

  if (inputs.authToken !== '') {
    const bearer = `Bearer ${inputs.authToken}`
    headers = { authorization: bearer }
  }

  const http = new HttpClient('forrest-upload-artifact/0.1', [], {
    keepAlive: true,
    headers: headers
  })

  const name = inputs.artifactName
  const root = searchResult.rootDirectory

  for (const path of searchResult.filesToUpload) {
    const relativePath = relative(root, path)
    const dstUrl = `${FORREST_HOST}/upload/${name}/${relativePath}`

    core.info(`Uploading ${relativePath}`)
    core.debug(`  - Destination: ${dstUrl}`)

    const fd = await open(path)
    const stream = fd.createReadStream()
    const resp = await http.sendStream('PUT', dstUrl, stream)

    const status = resp.message.statusCode
    const message = resp.message.statusMessage
    const sm = `${status} ${message}`

    core.debug(`  - Status: "${sm}"`)

    if (status != 201) {
      core.setFailed(`Server did not respond with "201 Created" but "${sm}"`)
      return
    }

    const publicUrl = resp.message.headers['content-location']

    core.debug(`  - Public URL: "${publicUrl}"`)

    if (publicUrl === undefined) {
      core.setFailed('Server did not provide a public URL in response')
      return
    }

    const desktopFilePath = path + `.desktop`
    const desktopFileContent = `[Desktop Entry]\nType=Link\nURL=${publicUrl}`

    await writeFile(desktopFilePath, desktopFileContent)

    core.debug(`  - Created: "${desktopFilePath}"`)

    await rm(path)

    core.debug(`  - Removed: "${path}"`)
  }
}
