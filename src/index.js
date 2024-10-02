import * as core from "@actions/core";
import { open, readFile, rm, writeFile } from "node:fs/promises";
import { HttpClient } from "@actions/http-client";
import { findFilesToUpload } from "./search";
import { relative } from "node:path";

function getInputs() {
  const name = core.getInput("name") || "artifact";
  const authToken = core.getInput("token");
  const includeHiddenFiles = core.getBooleanInput("include-hidden-files");
  const path = core.getInput("path", { required: true });

  return {
    artifactName: name,
    authToken: authToken,
    includeHiddenFiles: includeHiddenFiles,
    searchPath: path,
  };
}

function getApiUrl() {
  const url = process.env.FORREST_API_URL;

  if (url === undefined || url === "") {
    throw new Error("The FORREST_API_URL environment variable is not set");
  }

  return url;
}

async function getRunToken() {
  const path = process.env.FORREST_RUN_TOKEN_FILE;

  if (path === undefined || path === "") {
    throw new Error(
      "The FORREST_RUN_TOKEN_FILE environment variable is not set",
    );
  }

  const runToken = await readFile(path, { encoding: "utf8" });

  return runToken.trim();
}

export async function run() {
  const inputs = getInputs();
  const searchResult = await findFilesToUpload(
    inputs.searchPath,
    inputs.includeHiddenFiles,
  );

  const apiUrl = getApiUrl();
  const runToken = await getRunToken();

  let authorization = "Bearer " + runToken;

  if (inputs.authToken !== "") {
    authorization += " " + inputs.authToken;
  }

  const http = new HttpClient("forrest-upload-artifact/0.1", [], {
    headers: { authorization },
    keepAlive: true,
  });

  const name = inputs.artifactName;
  const root = searchResult.rootDirectory;

  let publicBaseUrl;

  for (const path of searchResult.filesToUpload) {
    const relativePath = relative(root, path);
    const dstUrl = `${apiUrl}/artifact/${name}/${relativePath}`;

    core.debug(`Uploading ${relativePath}`);
    core.debug(`  - Destination: ${dstUrl}`);

    const fd = await open(path);
    const stream = fd.createReadStream();
    const resp = await http.sendStream("PUT", dstUrl, stream);

    const status = resp.message.statusCode;
    const message = resp.message.statusMessage;
    const body = await resp.readBody();
    const sm = `${status} ${message}`;

    core.debug(`  - Status: "${sm}"`);

    if (status !== 201) {
      core.debug(`  - Body: "${body}"`);

      throw new Error(`Server did not respond with "201 Created" but "${sm}"`);
    }

    const publicUrl = resp.message.headers["content-location"];

    core.debug(`  - Public URL: "${publicUrl}"`);

    if (publicUrl === undefined) {
      throw new Error("Server did not provide a public URL in response");
    }

    core.info(`Artifact download URL: ${publicUrl}`);

    publicBaseUrl = publicUrl.slice(0, publicUrl.length - relativePath.length);

    const desktopFilePath = path + `.desktop`;
    const desktopFileContent = `[Desktop Entry]\nType=Link\nURL=${publicUrl}`;

    await writeFile(desktopFilePath, desktopFileContent);

    core.debug(`  - Created: "${desktopFilePath}"`);

    await rm(path);

    core.debug(`  - Removed: "${path}"`);
  }

  core.info(`Artifact base URL: ${publicBaseUrl}`);
  core.setOutput("artifact-url", publicBaseUrl);

  http.dispose();
}

run().catch((error) => {
  core.setFailed(error.message);
});
