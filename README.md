# Forrest Artifact Upload Action

```
                                    ┏━━━━━━━━━━━━━━━┓
                                    ┃      Run      ┃
                                    ┃    Forrest    ┃
                                    ┃      Run      ┃
                                    ┗━━━┯━━━━━━━┯━━━┛
```

GitHub Action that uploads artifacts to the local [Forrest Runner][forrest_app].

Uploaded files are replaced by [`.desktop`][dot_desktop_spec] files of
`Type=Link` with a `URL=` set to the public URL of the uploaded file. These
`.desktop` files can for example be uploaded in a subsequent
`actions/upload-artifact` call.

```yaml
name: Build Job

on: [push]

jobs:
  base:
    name: Base
    runs-on: [self-hosted, forrest, debian-base]
    steps:
      - name: Build
        run: make

      - uses: forrest-runner/upload-artifact@main
        with:
          path: build

      - uses: actions/upload-artifact@v4
        with:
          path: build
```

[forrest_app]: https://github.com/forrest-runner/
[dot_desktop_spec]:
  https://specifications.freedesktop.org/desktop-entry-spec/latest/
