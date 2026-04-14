### [3.7.1](https://github.com/dangeroustech/StreamDL/compare/v3.7.0...v3.7.1) (2026-04-14)


### 🐛 Bug Fixes

* replace nested rate-limit retry with loop and add missing docstrings ([31ef9b0](https://github.com/dangeroustech/StreamDL/commit/31ef9b0095b16d3003d168311b0ba2d6259272b9)), closes [#555](https://github.com/dangeroustech/StreamDL/issues/555) [#554](https://github.com/dangeroustech/StreamDL/issues/554)

## [3.7.0](https://github.com/dangeroustech/StreamDL/compare/v3.6.0...v3.7.0) (2026-04-14)


### 🎉 New Features

* add vod and vod_limit fields to channel config (Task 1 partial) ([7e8efa6](https://github.com/dangeroustech/StreamDL/commit/7e8efa609afd51819d69c1252872aa75cc0cf833))
* implement Twitch VOD download support ([af000db](https://github.com/dangeroustech/StreamDL/commit/af000db3c266c65654edf411b03878f5b1bcf16f))


### 📚 Documentation

* clarify -data flag is configurable in README VOD section ([77d898c](https://github.com/dangeroustech/StreamDL/commit/77d898c90a968f33ba2dc10bd212293d841deaff))


### ✍ Chore

* add CodeRabbit config to enable reviews on staging PRs ([87adf3f](https://github.com/dangeroustech/StreamDL/commit/87adf3f12044d42519c0b39ceb1ad953bfd01e30))
* **deps:** bump lodash from 4.17.21 to 4.18.1 ([#556](https://github.com/dangeroustech/StreamDL/issues/556)) ([e07ee5d](https://github.com/dangeroustech/StreamDL/commit/e07ee5d1e5346cb5721b72a49f0063005762e699))
* **deps:** bump pygments from 2.18.0 to 2.20.0 ([#536](https://github.com/dangeroustech/StreamDL/issues/536)) ([c6b17bb](https://github.com/dangeroustech/StreamDL/commit/c6b17bb5826e3df7a5caca60178e8b87321c0923))
* **deps:** bump pytest from 8.3.3 to 9.0.3 ([#543](https://github.com/dangeroustech/StreamDL/issues/543)) ([d2fe06c](https://github.com/dangeroustech/StreamDL/commit/d2fe06c74562cad67d372bbead1632757eed2efe))
* **deps:** bump requests from 2.32.3 to 2.33.0 ([#538](https://github.com/dangeroustech/StreamDL/issues/538)) ([866969c](https://github.com/dangeroustech/StreamDL/commit/866969cacc9ce0ff5021ac1b0c5883c2d344ddc8))
* **deps:** bump urllib3 from 2.2.3 to 2.6.3 ([#547](https://github.com/dangeroustech/StreamDL/issues/547)) ([a24bb52](https://github.com/dangeroustech/StreamDL/commit/a24bb5201dc89526e787623f03387a2841cbfb70))
* pin protobuf>=5.29.0 and ignore generated files in CodeRabbit ([2c02376](https://github.com/dangeroustech/StreamDL/commit/2c02376c5b12f21c38575b57dc6726192d22f18a))


### 🐛 Bug Fixes

* add server logs to VOD failure path and distinguish probe errors ([d3b9df3](https://github.com/dangeroustech/StreamDL/commit/d3b9df3aff42fbe9ac9b665eb146022dc34134d0))
* address CodeRabbit review findings ([a90bb2f](https://github.com/dangeroustech/StreamDL/commit/a90bb2f667b2099b2bc31f23aaa572d1f52f4f93))
* check RowsAffected in MarkVODCompleted and MarkVODFailed ([8768785](https://github.com/dangeroustech/StreamDL/commit/87687852b0d6e9ea5fa81987ca3b0e501597d947))
* clean stale VOD database before integration test Phase 5 ([ea82c0f](https://github.com/dangeroustech/StreamDL/commit/ea82c0f990d549ce01bf18bebb28eb12d483076b))
* lazy init VOD database on first use ([37559aa](https://github.com/dangeroustech/StreamDL/commit/37559aa9e15d20a3faa193092e5a4d4a819db510))
* make VOD integration test more robust ([8438861](https://github.com/dangeroustech/StreamDL/commit/84388610f0d941c37b60d10adf45a9d316140060))
* probe candidate VOD channels in integration test ([0db038d](https://github.com/dangeroustech/StreamDL/commit/0db038d86e1154a0e0720293e173b1e55e99ded5))
* quote shell variables and document in-progress VOD test trade-off ([c1126ad](https://github.com/dangeroustech/StreamDL/commit/c1126add103b569e12e7f67bb78b14f6c8276c01))
* release VOD claim on setup and resolution failures ([17a7856](https://github.com/dangeroustech/StreamDL/commit/17a78566d11e9de8089e8c3f52ab887c2e0a280c))
* replace ShouldDownloadVOD + MarkVODStarted with atomic ClaimVOD ([fe7fea2](https://github.com/dangeroustech/StreamDL/commit/fe7fea295b2a988a81edbbfe60cdd41cd82c8816))
* tighten VOD integration test file match to .mp4 ([4d7b0ac](https://github.com/dangeroustech/StreamDL/commit/4d7b0acb1b3fbf4ab0258ce8ff212debc0d07d4b))
* track VOD download goroutines for graceful shutdown ([a93a4c9](https://github.com/dangeroustech/StreamDL/commit/a93a4c94f577ef078bdfe6fa93533f540ea9115d))
* use .get() for format fields in yt-dlp fallback to avoid KeyError ([52b1fa1](https://github.com/dangeroustech/StreamDL/commit/52b1fa1ca5da91a0505ac72992e5c05ab0911611))
* use dedicated VOD channel in integration test ([91bac11](https://github.com/dangeroustech/StreamDL/commit/91bac118ff67decc6f65cfc97c820782f0f675e1))
* use teampgp as dedicated VOD integration test channel ([219892f](https://github.com/dangeroustech/StreamDL/commit/219892fce78e951dd682e8ba150ca09d74a04fed))

## [3.6.0](https://github.com/dangeroustech/StreamDL/compare/v3.5.1...v3.6.0) (2026-04-13)


### 🏭 Build

* **deps:** bump golang.org/x/net from 0.37.0 to 0.38.0 ([dfe5251](https://github.com/dangeroustech/StreamDL/commit/dfe5251a7feb8d90eab675a173bbf6ea12ca2085))


### 🎉 New Features

* add unit tests for config reader and improve error handling ([9b9601f](https://github.com/dangeroustech/StreamDL/commit/9b9601f41bab1f368598a018663899ab735ce95d))
* add unit tests for moveFile function and enhance cross-device handling ([2046aaa](https://github.com/dangeroustech/StreamDL/commit/2046aaaaf618439e65ac3692002a00f53917e099))
* enhance downloadStream function with retry logic and network resilience ([8947e7f](https://github.com/dangeroustech/StreamDL/commit/8947e7f1c2c62af3f5faa266c33fec4fa669f951))


### 📃 Refactor

* enhance entrypoint scripts to handle user/group creation and permissions based on root status ([7d2cf50](https://github.com/dangeroustech/StreamDL/commit/7d2cf505f34516b0625818411f3851cf45e0ce3e))
* enhance error handling and logging in downloadStream, moveFile, and gRPC connection management ([e4f66f5](https://github.com/dangeroustech/StreamDL/commit/e4f66f55788c11fb84a18e42d80a47dcb0be3b53))
* improve code readability and consistency in configuration and file handling tests ([30d79a5](https://github.com/dangeroustech/StreamDL/commit/30d79a558f9a18ff733e23f16194ed7901afd66b))
* improve entrypoint scripts with debug information and adjust permissions for .pdm-build directory ([fbfbff2](https://github.com/dangeroustech/StreamDL/commit/fbfbff299e2bcf3ab52f73d117296a9c5bcec24d))
* improve logging format and streamline code readability in streamdl_proto_srv.py ([d45c340](https://github.com/dangeroustech/StreamDL/commit/d45c340036484bdf0ed262e4331d0d1ceb047333))
* simplify entrypoint scripts by removing debug output and consolidating user/group creation steps ([f67994f](https://github.com/dangeroustech/StreamDL/commit/f67994f5b81802d7934e8471e2d45c782fdd144b))
* streamline downloadStream function and enhance logging ([4f70983](https://github.com/dangeroustech/StreamDL/commit/4f70983afddd132efd0e296025e580585ae2af79))
* streamline entrypoint script by removing redundant ownership changes and clarifying permissions for .venv ([88bcbee](https://github.com/dangeroustech/StreamDL/commit/88bcbee921d6e4d7e53cc867115741d8f7f14e9d))


### 🧪 Tests

* add end-to-end integration test for live stream download ([8f817b8](https://github.com/dangeroustech/StreamDL/commit/8f817b89d81e5034ee8d3d8873949c6d1b35fb93))


### 📚 Documentation

* add docstrings to Python server functions and classes ([98eea44](https://github.com/dangeroustech/StreamDL/commit/98eea44884464491245b29a308351f452b60e507))
* add FFmpeg resilience settings to README ([8a28341](https://github.com/dangeroustech/StreamDL/commit/8a283414f5b871fc2cf44dbe90230322f6c33f5f))


### ✍ Chore

* add --sarif option to Snyk scan parameters in deploy workflows ([627c6b3](https://github.com/dangeroustech/StreamDL/commit/627c6b31fe1aae39f5ce4cb55b905b555e272fe7))
* add category parameter for Snyk SARIF file in deploy workflows ([71d9730](https://github.com/dangeroustech/StreamDL/commit/71d973012182ec1509300d88f1e5118bf23d0f01))
* add docs/ to gitignore ([9ad1ade](https://github.com/dangeroustech/StreamDL/commit/9ad1adedad4b315eda746cf5ad8ecbcd52592f4f))
* add go.work file for Go module management ([8aa3642](https://github.com/dangeroustech/StreamDL/commit/8aa3642ddde6e8a79925f1cb505129106f300458))
* add go.work.sum file for dependency management ([a14c088](https://github.com/dangeroustech/StreamDL/commit/a14c088c8e30cb6dc99965a1ee0aa76d0ffa9119))
* add health checks and curl installation in Dockerfiles, implement health server in streamdl_proto_srv.py ([ba5199a](https://github.com/dangeroustech/StreamDL/commit/ba5199a478d8ddfb6be4f27c1ccd88edb4286462))
* **ci:** update action versions, Go, Python, and Node versions ([fc86f54](https://github.com/dangeroustech/StreamDL/commit/fc86f5496da0905d9b16d350ad7234b735da8d46))
* implement non-root user and directory permissions in Dockerfiles ([ab7fb75](https://github.com/dangeroustech/StreamDL/commit/ab7fb750d81fcf17d566c2206da30f197e2ef772))
* permissions debug ([624be49](https://github.com/dangeroustech/StreamDL/commit/624be491182092d47e8a83ab902f36f8dbaaa8a6))
* pin su-exec version in Dockerfile.client to ensure compatibility ([2879e47](https://github.com/dangeroustech/StreamDL/commit/2879e474cd5bc43b5007312cb63cca40b3bab2ed))
* remove exclusion of /usr/local/go/** from Snyk scan parameters in deploy workflows ([edd43a3](https://github.com/dangeroustech/StreamDL/commit/edd43a3dcf3c77f30e8fde9f078aeb216adca53e))
* remove go.work and go.work.sum files as they are no longer needed ([1a1c85d](https://github.com/dangeroustech/StreamDL/commit/1a1c85df5b15be988924aba68ccb32e044e7508c))
* rename Docker Scan to Snyk Scan and update scan parameters in deploy_staging.yml ([4e38833](https://github.com/dangeroustech/StreamDL/commit/4e38833ac66e1d275bcdbb0f038c8c2a1153f839))
* update category parameter for Snyk SARIF file in deploy workflows to include event name ([27c0b55](https://github.com/dangeroustech/StreamDL/commit/27c0b55a907dbac49f9a2cfc15d41270940f3b2d))
* update category parameter for Snyk SARIF file in deploy workflows to remove redundant prefixes ([1dafbcd](https://github.com/dangeroustech/StreamDL/commit/1dafbcdbaacfe25f6a276490ceb89517f0fed5aa))
* update ffmpeg version in Dockerfile.client from 7.1.1 to 8.0 ([9ac837d](https://github.com/dangeroustech/StreamDL/commit/9ac837de6f18e3226674e9d2bd5149097c95fa17))
* update Go version and dependencies in Dockerfile and go.mod ([8cd053e](https://github.com/dangeroustech/StreamDL/commit/8cd053e0de91f7355e152c6859271ce8eeff2dfe))
* update Snyk scan parameters in deploy workflows to include app vulnerabilities and exclude specific paths ([bc00136](https://github.com/dangeroustech/StreamDL/commit/bc001368ad67ce6f8eca6626cc99a02176f23937))


### 🐛 Bug Fixes

* --twitch--disable-ads is now the default ([c645c01](https://github.com/dangeroustech/StreamDL/commit/c645c0194e7acf6265b8f95d03cfca1a51f7f31c))
* add sync.RWMutex for urls map, protect delete in downloadStream ([f2c8567](https://github.com/dangeroustech/StreamDL/commit/f2c8567aba37d432bc346e4e962ba4b81009aa43))
* address CodeRabbit PR [#507](https://github.com/dangeroustech/StreamDL/issues/507) review items [#4](https://github.com/dangeroustech/StreamDL/issues/4),7-12 ([d96852d](https://github.com/dangeroustech/StreamDL/commit/d96852d325660391ff7a22cc28854206571718f2))
* address remaining CodeRabbit PR [#507](https://github.com/dangeroustech/StreamDL/issues/507) review items [#13](https://github.com/dangeroustech/StreamDL/issues/13)-18 ([5269d40](https://github.com/dangeroustech/StreamDL/commit/5269d40ebb1b95d92ea42db7bda44eb8009f5c40)), closes [#13-18](https://github.com/dangeroustech/StreamDL/issues/13-18)
* address second round of CodeRabbit review comments ([ab2db99](https://github.com/dangeroustech/StreamDL/commit/ab2db99df40b7d3f481f5e16240e14b76d316793))
* **ci:** drop Python 3.14 from test matrix (lxml lacks 3.14 wheels) ([1bd5ae1](https://github.com/dangeroustech/StreamDL/commit/1bd5ae1c3e413f652fac7f12da342d921048c221))
* **ci:** exclude validator's own grep line from action version check ([e314026](https://github.com/dangeroustech/StreamDL/commit/e314026deb66e7c0123671ba4a001d6f6c9211bf))
* **ci:** pin Snyk action to v1, lower severity threshold, quote GITHUB_STEP_SUMMARY ([52aa178](https://github.com/dangeroustech/StreamDL/commit/52aa178e16f2d47442c5f1bdeb477be2c463edc3))
* **ci:** use setup-uv@v7 (v8 major tag not yet available) ([03412e6](https://github.com/dangeroustech/StreamDL/commit/03412e6855d61414927d3e3dd61d6c8151946a17))
* **deps:** pin go-jose/v4 to v4.1.4 to resolve CVE-2026-34986 ([35ab99a](https://github.com/dangeroustech/StreamDL/commit/35ab99a3488fc21383f5748b69089b1aec6c4dc7))
* **deps:** update grpc and transitive deps to resolve Snyk vulnerabilities ([e31c62a](https://github.com/dangeroustech/StreamDL/commit/e31c62a92a7a19046695a03500404c798186374d))
* ensure user cleanup in downloadStream goroutine ([d9998f8](https://github.com/dangeroustech/StreamDL/commit/d9998f8e00a157817ed12499f2e393983630e2d8))
* increase default FFMPEG reconnect delay from 5 to 15 seconds ([047e290](https://github.com/dangeroustech/StreamDL/commit/047e29072be2ed4d0f601da716fe0989058f7792))
* protect urls map reads in ticker loop with urlsMu RLock ([a2b8955](https://github.com/dangeroustech/StreamDL/commit/a2b8955eae068c3f7d68260d6cdda1c0884f5f15))
* protect urls map writes in ticker loop with urlsMu ([b36a499](https://github.com/dangeroustech/StreamDL/commit/b36a499a255f9768b008e1446aa793ce5761bd3a))
* update curl package version in Dockerfile.server ([31f74d5](https://github.com/dangeroustech/StreamDL/commit/31f74d5692c14c1cb98a6be7d771f4a01405b4cd))
* update curl version in Dockerfile.client from 8.14.1-r1 to 8.14.1-r2 ([296b3cb](https://github.com/dangeroustech/StreamDL/commit/296b3cb9915d798c339030ff24d60e8a5c9e3117))
* update gRPC client connection method and increase timeout ([e9cdc75](https://github.com/dangeroustech/StreamDL/commit/e9cdc75cbc966c0a0916de65851accfb9d0e95f7))
* update ownership and permissions for app directory and .venv in entrypoint script ([2fdc5db](https://github.com/dangeroustech/StreamDL/commit/2fdc5dba973dcf84c128eb796c5861f73b00e92e))
* yt_dlp error handling bug that caused some plugins to always fail ([d816e98](https://github.com/dangeroustech/StreamDL/commit/d816e986ea4d601d9b4f84854de6c1132622e24a))

### [3.5.1](https://github.com/dangeroustech/StreamDL/compare/v3.5.0...v3.5.1) (2025-08-11)


### ✍ Chore

* **release:** update dependencies and bump version to 3.5.0 ([847aca3](https://github.com/dangeroustech/StreamDL/commit/847aca3f52374167f2936e2ec6c204d2fe7f45ed))

## [3.5.0](https://github.com/dangeroustech/StreamDL/compare/v3.4.1...v3.5.0) (2025-03-19)


### 🎉 New Features

* add umask info to docs and file mover logic ([2f06996](https://github.com/dangeroustech/StreamDL/commit/2f069968a6109a87a84e8850b0b1a5b266a949dc))


### 📚 Documentation

* clarify dir permissions language ([d4251f2](https://github.com/dangeroustech/StreamDL/commit/d4251f22bff44e2d28eadf14dabbbc32554ce1be))
* update docs with UMASK, PUID, and PGID information ([79cdd6c](https://github.com/dangeroustech/StreamDL/commit/79cdd6cd6ef85acd41f796f2350a813319bcf1e2))


### 🐛 Bug Fixes

* add UMASK output to startup for confirmation ([1d80209](https://github.com/dangeroustech/StreamDL/commit/1d8020934028dc0cd9c5e209c865b75077d47354))
* create directories from scratch with correct permissions ([bcf6951](https://github.com/dangeroustech/StreamDL/commit/bcf6951da9b4f175a0f164017b821be6612e7272))
* stop changing config directory permissions ([fa1a233](https://github.com/dangeroustech/StreamDL/commit/fa1a233ab2c2cc378dd5e1dbcbb0f03a9993964a))


### ✍ Chore

* bump ffmpeg version to 7.1.1 ([b644293](https://github.com/dangeroustech/StreamDL/commit/b64429351c5ab533b86212a90c7af6bc155bbb7b))
* bump grpcio fixes [#475](https://github.com/dangeroustech/StreamDL/issues/475) ([b5ef1ab](https://github.com/dangeroustech/StreamDL/commit/b5ef1ab45a47583a4dc38e92545423ac649f552d))
* bump official go version to 1.24.1 ([5af2b19](https://github.com/dangeroustech/StreamDL/commit/5af2b194b1a10cd6f952485e4b9cdaa019da25b4))
* deps update ([cadf71f](https://github.com/dangeroustech/StreamDL/commit/cadf71fc276409cf6bcc7c7a42a39eaf03c33c6f))
* fixes [#474](https://github.com/dangeroustech/StreamDL/issues/474) ([056e845](https://github.com/dangeroustech/StreamDL/commit/056e84547de397cb1a336ddfdf36ce8aa1eea859))
* intermediate commit ([dbc8448](https://github.com/dangeroustech/StreamDL/commit/dbc8448a4fe202416cf93b5a2cc48422db619e7a))
* linting ([5f32536](https://github.com/dangeroustech/StreamDL/commit/5f32536588be83ca47453b8b47aa763b0ef3e13f))
* linting ([165c9bc](https://github.com/dangeroustech/StreamDL/commit/165c9bc621954b047ba4d21ae3fbaf8fb228e523))
* update linter config ([818a7a4](https://github.com/dangeroustech/StreamDL/commit/818a7a4c0ae07b75072d67658d6db8ce053ea3c7))
* update linters ([e3c2a2e](https://github.com/dangeroustech/StreamDL/commit/e3c2a2e4358464687bbde0a8fd3eae0633505c74))

### [3.4.1](https://github.com/dangeroustech/StreamDL/compare/v3.4.0...v3.4.1) (2025-03-16)


### 📚 Documentation

* fix markdown formatting ([05ededb](https://github.com/dangeroustech/StreamDL/commit/05ededb3a66e01f0a3230d1c3e3ed8f8085d8c91))
* remove CodeQL badge ([7b78e3b](https://github.com/dangeroustech/StreamDL/commit/7b78e3b20aee43d25d8da716aae0aaaf0cd36a7d))

## [3.4.0](https://github.com/dangeroustech/StreamDL/compare/v3.3.9...v3.4.0) (2025-03-15)


### ✍ Chore

* add comment for later dev ([48511b9](https://github.com/dangeroustech/StreamDL/commit/48511b94b49c25b877a1159b91ba31964fc8e9fb))
* logging progress ([9db5e86](https://github.com/dangeroustech/StreamDL/commit/9db5e865f3a0e873d50c895e6c7e0a3feacd1c62))


### 🐛 Bug Fixes

* error logging ([ed54b50](https://github.com/dangeroustech/StreamDL/commit/ed54b500cd22fb5759a18233ec9703ee3b18af3a))
* less annoying logs ([6aaed7b](https://github.com/dangeroustech/StreamDL/commit/6aaed7b3ad6c1084e9e1bb331d23d6332d584abf))
* set default tick time to 60 per docs ([baac56a](https://github.com/dangeroustech/StreamDL/commit/baac56a913570873588c2d08872b220538b7617b))
* typo in CONTRIBUTING ([3d33653](https://github.com/dangeroustech/StreamDL/commit/3d336532bc8e737953ce787cae4c39d1915335b2))


### 📃 Refactor

* more sensible logging ([15df76b](https://github.com/dangeroustech/StreamDL/commit/15df76bb01a27e15dc84426b5a03dc0a8d27af8c))
* move 429 handling code to client to allow for proper backoff loop ([ccf000c](https://github.com/dangeroustech/StreamDL/commit/ccf000cc66717b19a61009e6efbe2884390f4570))
* yt_dlp logging structure ([0fc0ba9](https://github.com/dangeroustech/StreamDL/commit/0fc0ba9673a75db5642e23aca5a6e0c454b46054))


### 🎉 New Features

* add batch time flag for URL checks and enhance logging ([df63384](https://github.com/dangeroustech/StreamDL/commit/df633845de197296634097387799ac75bebb9016))

### [3.3.9](https://github.com/dangeroustech/StreamDL/compare/v3.3.8...v3.3.9) (2025-03-15)


### 🐛 Bug Fixes

* maybe this will sort the yt_dlp errors ([796e259](https://github.com/dangeroustech/StreamDL/commit/796e2593fd399ed257e3aba16bb4d06d549161df))

### [3.3.8](https://github.com/dangeroustech/StreamDL/compare/v3.3.7...v3.3.8) (2025-03-15)


### 📃 Refactor

* yt_dlp logging structure ([f203a63](https://github.com/dangeroustech/StreamDL/commit/f203a636b3f7d78f2ab76a440299aecf10e1bc3b))

### [3.3.7](https://github.com/dangeroustech/StreamDL/compare/v3.3.6...v3.3.7) (2025-03-15)


### 🐛 Bug Fixes

* yt_dlp version error ([1d0a5c6](https://github.com/dangeroustech/StreamDL/commit/1d0a5c68ff6f0e4677544f84583d24b653ec9115))

### [3.3.6](https://github.com/dangeroustech/StreamDL/compare/v3.3.5...v3.3.6) (2025-03-15)


### 🐛 Bug Fixes

* restructure error handling for yt_dlp ([75a077a](https://github.com/dangeroustech/StreamDL/commit/75a077afb260a79943d5608b781d8c6d64f5ecc8))

### [3.3.5](https://github.com/dangeroustech/StreamDL/compare/v3.3.4...v3.3.5) (2025-03-15)


### 🐛 Bug Fixes

* yt_dlp logging ([8e5bd0f](https://github.com/dangeroustech/StreamDL/commit/8e5bd0f08fb06642c26dccaeb644bff67dfa736d))

### [3.3.4](https://github.com/dangeroustech/StreamDL/compare/v3.3.3...v3.3.4) (2025-03-15)


### 🐛 Bug Fixes

* add default to TICK_TIME in entrypoint script ([98cbf5a](https://github.com/dangeroustech/StreamDL/commit/98cbf5a89e3f24fbc8a8a3cf54569859d10d66e6))
* proper yaml package import ([eb1d01e](https://github.com/dangeroustech/StreamDL/commit/eb1d01e7fb8eb63e892a4a2ebb8821686d221fa9))
* properly add log-level to flags ([c1379cc](https://github.com/dangeroustech/StreamDL/commit/c1379cc5634f89c38d02b1ce85966c4811b8c4fd))


### ✍ Chore

* fix line length linter error ([e1ddfda](https://github.com/dangeroustech/StreamDL/commit/e1ddfdaa3dc366568ce579f76f902149f60ea5f6))
* more consistent logging ([6ccf783](https://github.com/dangeroustech/StreamDL/commit/6ccf783f4598592f47b267ad5f74addb51c79872))

### [3.3.3](https://github.com/dangeroustech/StreamDL/compare/v3.3.2...v3.3.3) (2025-03-12)


### 🐛 Bug Fixes

* add curl-cffi for impersonation ([5c387e5](https://github.com/dangeroustech/StreamDL/commit/5c387e5c887ac712102d44a41c1505f1dcea0ea2))

### [3.3.2](https://github.com/dangeroustech/StreamDL/compare/v3.3.1...v3.3.2) (2025-03-09)


### 🏭 Build

* further SARIF test changes ([46ee9e6](https://github.com/dangeroustech/StreamDL/commit/46ee9e6da9a4329412e3ed883da07dc7031cb4fa))

### [3.3.1](https://github.com/dangeroustech/StreamDL/compare/v3.3.0...v3.3.1) (2025-03-09)


### 🏭 Build

* attempt to reduce number of SARIF scans to allow successful upload ([d2e16c2](https://github.com/dangeroustech/StreamDL/commit/d2e16c257c93f992b9992936fcc4d29a0baa771b))

## [3.3.0](https://github.com/dangeroustech/StreamDL/compare/v3.2.21...v3.3.0) (2025-03-09)


### 🎉 New Features

* version bumping to align to SECURITY.md ([774528c](https://github.com/dangeroustech/StreamDL/commit/774528c27980ac0087255059871d4d0ad2307908))

### [3.2.21](https://github.com/dangeroustech/StreamDL/compare/v3.2.20...v3.2.21) (2025-03-09)


### 🐛 Bug Fixes

* correct security version support following latest round of dep updates ([19293d8](https://github.com/dangeroustech/StreamDL/commit/19293d84d1c292f2bc1bdf2a692a35077c8d3413))

### [3.2.20](https://github.com/dangeroustech/StreamDL/compare/v3.2.19...v3.2.20) (2025-03-09)


### 📚 Documentation

* update SECURITY.md to deprecate support for non-3.x.x versions ([48a6d20](https://github.com/dangeroustech/StreamDL/commit/48a6d201f9c44ea94fda67bbe7dd299803de840e))

### [3.2.19](https://github.com/dangeroustech/StreamDL/compare/v3.2.18...v3.2.19) (2025-03-09)


### ✍ Chore

* dependabot not working with uv yet so manually updatring core deps ([81e8438](https://github.com/dangeroustech/StreamDL/commit/81e84385d1b3c6e0cdce47eab90e4f94afd1c9d4))

### [3.2.18](https://github.com/dangeroustech/StreamDL/compare/v3.2.17...v3.2.18) (2025-03-09)


### ✍ Chore

* bump go deps ([95c17d0](https://github.com/dangeroustech/StreamDL/commit/95c17d0da773186851bcdf8b55becd6dcd9183aa))
* further bump go deps ([923f6ca](https://github.com/dangeroustech/StreamDL/commit/923f6cabc4d2bb0c2bb4ec9575e69310f1674bdd))
* go mod tidy ([9e42ddb](https://github.com/dangeroustech/StreamDL/commit/9e42ddbc986fc07dad089df66533e1e2c76e0c5a))
* update uv deps ([6fdae6b](https://github.com/dangeroustech/StreamDL/commit/6fdae6b97bb3ec4b28490a7838ead8a864753aa3))


### 🐛 Bug Fixes

* bump go version in client dockerfile ([809c98a](https://github.com/dangeroustech/StreamDL/commit/809c98ab4878acb1083011110b61d87925e7f7cb))


### 🧪 Tests

* update go PR test versions ([1c40468](https://github.com/dangeroustech/StreamDL/commit/1c40468416d17845e8ba6191647cd762fc8b8614))

### [3.2.17](https://github.com/dangeroustech/StreamDL/compare/v3.2.16...v3.2.17) (2025-03-09)


### ✍ Chore

* key syntax update ([72f34c3](https://github.com/dangeroustech/StreamDL/commit/72f34c380dcee17035dc399497c486c5981b7df9))


### 📚 Documentation

* remove old usage content ([ddade70](https://github.com/dangeroustech/StreamDL/commit/ddade70b93c114c3ef5a4c3ab59fcee4de2c3841))
* update for uv usage ([bb4261a](https://github.com/dangeroustech/StreamDL/commit/bb4261a15dcc770162c790032d725b591500b8a6))
* update README with current flags ([8497faa](https://github.com/dangeroustech/StreamDL/commit/8497faaed0db643e5cf679eb5d47090a51b52ebd))

### [3.2.16](https://github.com/dangeroustech/StreamDL/compare/v3.2.15...v3.2.16) (2024-11-01)

### [3.2.15](https://github.com/dangeroustech/StreamDL/compare/v3.2.14...v3.2.15) (2024-11-01)


### ✍ Chore

* remove unused comments ([cdc9aa8](https://github.com/dangeroustech/StreamDL/commit/cdc9aa8e43c0969d55243484504ccee3759f4254))

### [3.2.14](https://github.com/dangeroustech/StreamDL/compare/v3.2.13...v3.2.14) (2024-11-01)


### ✍ Chore

* update uv build version ([9d1b305](https://github.com/dangeroustech/StreamDL/commit/9d1b3051fe6777f49c245423a2c850f841af93b7))


### 🐛 Bug Fixes

* add HTTP 429 error handling and backoff ([925519f](https://github.com/dangeroustech/StreamDL/commit/925519febf76292df5bd5a9a05d2833004dc7734))

### [3.2.13](https://github.com/dangeroustech/StreamDL/compare/v3.2.12...v3.2.13) (2024-10-29)


### 📚 Documentation

* correct typo ([d0bafd7](https://github.com/dangeroustech/StreamDL/commit/d0bafd775853395d8785b5083464ea67696c649d))

### [3.2.12](https://github.com/dangeroustech/StreamDL/compare/v3.2.11...v3.2.12) (2024-10-29)

### [3.2.11](https://github.com/dangeroustech/StreamDL/compare/v3.2.10...v3.2.11) (2024-10-29)


### 📃 Refactor

* move to uv for deps ([dfc7826](https://github.com/dangeroustech/StreamDL/commit/dfc78260baaf2f7337dd91a88f086307b7f1a2e0))


### ✍ Chore

* fix linter ([1ebcc48](https://github.com/dangeroustech/StreamDL/commit/1ebcc4866ac510a61f30ce1f4ce82542cc587bc8))
* fix linter errors ([878734b](https://github.com/dangeroustech/StreamDL/commit/878734b5198cc129e908a255583ff41a2fd90229))
* update software versions ([25037d6](https://github.com/dangeroustech/StreamDL/commit/25037d60b83ef18ebc9a09143dec3d88375648f3))


### 🧪 Tests

* update go versions ([8a16b5d](https://github.com/dangeroustech/StreamDL/commit/8a16b5d49971f454d523dabf01a931a5785aa4b2))
* update lts ubuntu version ([5021e14](https://github.com/dangeroustech/StreamDL/commit/5021e14f94d258558a13dfa58f9035a58629a5de))


### 🐛 Bug Fixes

* add more uv ([6301e9d](https://github.com/dangeroustech/StreamDL/commit/6301e9df76f61ecd9b289eed1a957f59e265b05a))
* add uv to dockerfile ([9ca9a23](https://github.com/dangeroustech/StreamDL/commit/9ca9a2380c4d9ce493700e6db65ba881c52b15e5))
* allow changelog job to write ([6df0485](https://github.com/dangeroustech/StreamDL/commit/6df04858af9eae5e65b7762dbe3a5d00a5d9d27e))
* deps file copy ([373337f](https://github.com/dangeroustech/StreamDL/commit/373337f7880cc6a58aec701dd6d6f275088e2b14))
* docker server build ([b4c9b28](https://github.com/dangeroustech/StreamDL/commit/b4c9b281b045229df61a3b8ac73b46d260015bd2))
* env vars ([e689690](https://github.com/dangeroustech/StreamDL/commit/e68969032fd1f2ca2dff2932c8b93e50e49b5a76))
* no pytest ([c83d70d](https://github.com/dangeroustech/StreamDL/commit/c83d70dc29ccd0ed6e688d1913094197037f96ec))
* quote localhost ([9b4988e](https://github.com/dangeroustech/StreamDL/commit/9b4988edce0ac27b20bed4be0f07f7ffda0646f7))
* reduce python versions by 1 ([931b13f](https://github.com/dangeroustech/StreamDL/commit/931b13f3286c34addc92e00b1ab4054bc41daf4f))
* update changelog release ([6c860ec](https://github.com/dangeroustech/StreamDL/commit/6c860ec62240546a4f8f214ddd740fbd1f261727))

### [3.2.10](https://github.com/dangeroustech/StreamDL/compare/v3.2.9...v3.2.10) (2024-10-29)


### ✍ Chore

* consolidate container layers ([c186f94](https://github.com/dangeroustech/StreamDL/commit/c186f94aeffce1a0a243cd89436ce6b6491f13e4))

### [3.2.9](https://github.com/dangeroustech/StreamDL/compare/v3.2.8...v3.2.9) (2024-10-29)


### ✍ Chore

* deps update ([ebee08b](https://github.com/dangeroustech/StreamDL/commit/ebee08bd90d914a03a54c7937a3da7fea18e28e8))

### [3.2.8](https://github.com/dangeroustech/StreamDL/compare/v3.2.7...v3.2.8) (2024-10-29)


### ✍ Chore

* **deps:** bump golang.org/x/net from 0.17.0 to 0.23.0 ([434fadd](https://github.com/dangeroustech/StreamDL/commit/434fadd7759652a23a1e11545ef5a96a170ee4f9))

### [3.2.7](https://github.com/dangeroustech/StreamDL/compare/v3.2.6...v3.2.7) (2024-10-29)


### ✍ Chore

* **deps:** bump idna from 3.6 to 3.7 ([f30e245](https://github.com/dangeroustech/StreamDL/commit/f30e2452d98685a0c228540223c1cd1a0195c549))

### [3.2.6](https://github.com/dangeroustech/StreamDL/compare/v3.2.5...v3.2.6) (2024-10-29)

### [3.2.5](https://github.com/dangeroustech/StreamDL/compare/v3.2.4...v3.2.5) (2024-10-29)


### 🐛 Bug Fixes

* Dockerfile.server to reduce vulnerabilities ([3f8aa92](https://github.com/dangeroustech/StreamDL/commit/3f8aa925022ff2857ccb91a3a10c720e42aba8cf))

### [3.2.4](https://github.com/dangeroustech/StreamDL/compare/v3.2.3...v3.2.4) (2024-03-30)


### 🐛 Bug Fixes

* correct logging output ([7afcd18](https://github.com/dangeroustech/StreamDL/commit/7afcd183aea613e67378bf1244227a0a5565d472))
* log format errors ([27c538c](https://github.com/dangeroustech/StreamDL/commit/27c538c753bb50d6640c47e58679f6a172b4e89e))
* typo ([0e367ac](https://github.com/dangeroustech/StreamDL/commit/0e367ac9bfc000d3cff395b538d7b58699ec83ab))
* typo ([3291c91](https://github.com/dangeroustech/StreamDL/commit/3291c91b4505ad5949f6d971619b2a3a84f751f2))

### [3.2.3](https://github.com/dangeroustech/StreamDL/compare/v3.2.2...v3.2.3) (2024-03-30)


### 🤖 CI/CD

* fix tag ([c9e97db](https://github.com/dangeroustech/StreamDL/commit/c9e97db33c38ade9a566b67ce67ac669f878efab))
* fix tag v2 ([99578e3](https://github.com/dangeroustech/StreamDL/commit/99578e3bdc980823b8f7df1dabdaf343f43bf880))
* must login to dockerhub ([f1782d8](https://github.com/dangeroustech/StreamDL/commit/f1782d8f4f8e3465fd2f2a0a70c63c84a44b3938))
* push tagged unstable container builds for testing ([8de2da7](https://github.com/dangeroustech/StreamDL/commit/8de2da7bd5a686b92a32e3d25957974e8657ecf4))
* we don't need to build on 2 different host OSes ([b0a0f08](https://github.com/dangeroustech/StreamDL/commit/b0a0f084d7ef4065499668e20a156cc1ebe226ec))


### 🐛 Bug Fixes

* correct timestamp because windows doesn't like colons ([68529da](https://github.com/dangeroustech/StreamDL/commit/68529daed1722d862b35ad061ff6070c04c98571))
* read config on each loop ([d3b398f](https://github.com/dangeroustech/StreamDL/commit/d3b398f16f8d862b0dc41a031e286b21ca719acf))
* set config location to a dir so the files updates automatically ([da5e1d0](https://github.com/dangeroustech/StreamDL/commit/da5e1d09ae2188fb4043ba8a70e1103c6cfe6cda))
* should use unbuffered channels now, config file can change in size ([9b44e3d](https://github.com/dangeroustech/StreamDL/commit/9b44e3debcfabae83b03d266ed0b81528c505acc))
* use common output separators ([ed427be](https://github.com/dangeroustech/StreamDL/commit/ed427be089ac75207b984ca42d6575c56e7a981f))

### [3.2.2](https://github.com/dangeroustech/StreamDL/compare/v3.2.1...v3.2.2) (2024-03-27)


### 🐛 Bug Fixes

* bump setup-go action to v5 for node16 deprecation ([b654621](https://github.com/dangeroustech/StreamDL/commit/b654621a89f8fadeefb469d1a67dacbcfa983977))
* drop python from 3.13 to 3.12 ([66d515b](https://github.com/dangeroustech/StreamDL/commit/66d515b7f14dbabdc871116c3318bd5f33f0812e))
* formatting to trigger some testing ([d59b9ab](https://github.com/dangeroustech/StreamDL/commit/d59b9ab9d796f218edcf991ddaab16e27e1900aa))

### [3.2.1](https://github.com/dangeroustech/StreamDL/compare/v3.2.0...v3.2.1) (2024-03-27)


### 🐛 Bug Fixes

* bump upper limits of python/go versions tested ([2639259](https://github.com/dangeroustech/StreamDL/commit/2639259064f3d442e4e55f40ba4330aeff83395e))


### 🤖 CI/CD

* raise snyk threshold to address error ([50f4c5b](https://github.com/dangeroustech/StreamDL/commit/50f4c5b2e1be764b7a0ede6eed4582f9a3e3f0cf))
* update release action ([57f962d](https://github.com/dangeroustech/StreamDL/commit/57f962dbd21e1b2b490ef6d8871d7d142fc97983))

## [3.2.0](https://github.com/dangeroustech/StreamDL/compare/v3.1.25...v3.2.0) (2024-03-26)


### 🎉 New Features

* add ability for user to specify yt_dlp quality ([0c6473e](https://github.com/dangeroustech/StreamDL/commit/0c6473e04bd0778a6cdfebc59d2afe027a5a5405))


### 🐛 Bug Fixes

* add docker healthcheck ([45b1ba9](https://github.com/dangeroustech/StreamDL/commit/45b1ba95a97edd8421af7814aeaa3be6e292ee18))
* add yt_dlp for fallback ([9059652](https://github.com/dangeroustech/StreamDL/commit/9059652008ac229d32a43927dbad09770b4a54fa))
* better error logging with yt_dlp ([19b832e](https://github.com/dangeroustech/StreamDL/commit/19b832e146413fa1dc3807c1755f4c7ebe837179))
* correct formatting and sorting on the users array ([28a29d6](https://github.com/dangeroustech/StreamDL/commit/28a29d62dbe1f7b729bead1619eefa6e5ba30a29))
* deprecated compose config ([81a01f3](https://github.com/dangeroustech/StreamDL/commit/81a01f3b71a1f9942b63db57f0844f2013f816f1))
* formatting ([45a37df](https://github.com/dangeroustech/StreamDL/commit/45a37df748471d908bdd735a5d218b1417443015))
* incorrect config example ([eb8117b](https://github.com/dangeroustech/StreamDL/commit/eb8117bfcf892a1a9caa16dae02ac3359d460482))
* lint linter config ([ed39266](https://github.com/dangeroustech/StreamDL/commit/ed392665a0af8339a6f58a52beed85f863e30d9f))
* warn is deprecated ([a033b15](https://github.com/dangeroustech/StreamDL/commit/a033b1538c80406d55e6ea4451e26f53f2bdd0e3))


### 📚 Documentation

* add more sensible examples ([08b8fcc](https://github.com/dangeroustech/StreamDL/commit/08b8fcca49961c6e59bb06bee6e2d758bcec7898))
* add paragraph on .env usage ([d91f75d](https://github.com/dangeroustech/StreamDL/commit/d91f75d4defbe4caeacfe363395bc76ddd6a1c06))
* use stable tag in example compose file ([35ef24a](https://github.com/dangeroustech/StreamDL/commit/35ef24a8efad8cf6fdd217b84dd546354394ec8c))


### 📃 Refactor

* fix deps ([7373b02](https://github.com/dangeroustech/StreamDL/commit/7373b027b96c6e1efe080f68f7867ab8e00e64e6))
* gofmt ([775ac32](https://github.com/dangeroustech/StreamDL/commit/775ac3265837852e359dd201a96ded49052d2922))
* linting ([e9269fa](https://github.com/dangeroustech/StreamDL/commit/e9269fa281fa9f5a1fcd2ca6c1e3e1834dda81bf))
* move file code in another file ([5c6cf36](https://github.com/dangeroustech/StreamDL/commit/5c6cf36a5413d8e3b869688311bd5f56634c33d7))
* need a better way of doing this healthcheck ([af68237](https://github.com/dangeroustech/StreamDL/commit/af682375fcae91d7efc2ef30626665bb49887871))
* remove env vars in favour of the .env file method ([8535755](https://github.com/dangeroustech/StreamDL/commit/85357557219e34b9fd41f33729d604489b3a3d8f))


### ✍ Chore

* add example .env file ([8ff0a2b](https://github.com/dangeroustech/StreamDL/commit/8ff0a2be4a0326c07b8a014e43db29f9543823f3))
* add todo ([9d9bd89](https://github.com/dangeroustech/StreamDL/commit/9d9bd8900572623d327d079531ba534c2e35d079))
* **deps:** bump google.golang.org/protobuf from 1.30.0 to 1.33.0 ([f7aa4c4](https://github.com/dangeroustech/StreamDL/commit/f7aa4c4092ab449e748b382e78794c2c2b940ace))
* error check ([6a9d6c2](https://github.com/dangeroustech/StreamDL/commit/6a9d6c2a0b542910f156fc9f840b52c072a52566))
* formatting ([b822e43](https://github.com/dangeroustech/StreamDL/commit/b822e438a2015091cb42fa830729b046eec057bb))
* linting idk ([d069605](https://github.com/dangeroustech/StreamDL/commit/d069605947b53b955be7c78ad286d9cfc79874d8))
* remove duplicated env var ([baf9371](https://github.com/dangeroustech/StreamDL/commit/baf9371e31c75cc2d0efda22b1d873c8a3f0c628))
* remove todo ([3f4fab6](https://github.com/dangeroustech/StreamDL/commit/3f4fab6eb1fd252c0ba7216fc3725de083167f5d))

### [3.1.25](https://github.com/dangeroustech/StreamDL/compare/v3.1.24...v3.1.25) (2024-03-26)

### [3.1.24](https://github.com/dangeroustech/StreamDL/compare/v3.1.23...v3.1.24) (2024-01-29)


### ✍ Chore

* **deps:** bump golang.org/x/crypto from 0.14.0 to 0.17.0 ([24920a7](https://github.com/dangeroustech/StreamDL/commit/24920a7c0eb223e1df1396c919641f72a86f6dd1))

### [3.1.23](https://github.com/dangeroustech/StreamDL/compare/v3.1.22...v3.1.23) (2024-01-29)


### 🤖 CI/CD

* update action versions ([1280229](https://github.com/dangeroustech/StreamDL/commit/1280229c8612518dae98e3a43ef619436eed57b0))

### [3.1.22](https://github.com/dangeroustech/StreamDL/compare/v3.1.21...v3.1.22) (2024-01-29)


### ✍ Chore

* **deps:** bump pycryptodome from 3.18.0 to 3.19.1 ([66c9ca3](https://github.com/dangeroustech/StreamDL/commit/66c9ca36cb2456cfbc2be06b63ab9f09cc9096b3))

### [3.1.21](https://github.com/dangeroustech/StreamDL/compare/v3.1.20...v3.1.21) (2024-01-29)

### [3.1.20](https://github.com/dangeroustech/StreamDL/compare/v3.1.19...v3.1.20) (2023-12-08)


### 🧪 Tests

* update youtube 404 test ([259eb64](https://github.com/dangeroustech/StreamDL/commit/259eb64d754e8aa4ba2bfe0a89f843dc9b956eac))

### [3.1.19](https://github.com/dangeroustech/StreamDL/compare/v3.1.18...v3.1.19) (2023-12-08)


### 🐛 Bug Fixes

* Dockerfile.client to reduce vulnerabilities ([8c22881](https://github.com/dangeroustech/StreamDL/commit/8c228817d38980eaea46d050e69e3bbc11c649cf))

### [3.1.18](https://github.com/dangeroustech/StreamDL/compare/v3.1.17...v3.1.18) (2023-10-26)


### ✍ Chore

* **deps:** bump google.golang.org/grpc from 1.53.0 to 1.56.3 ([d4f6d68](https://github.com/dangeroustech/StreamDL/commit/d4f6d68035235fbc25d4c322691155abe93b47b2))

### [3.1.17](https://github.com/dangeroustech/StreamDL/compare/v3.1.16...v3.1.17) (2023-10-24)

### [3.1.16](https://github.com/dangeroustech/StreamDL/compare/v3.1.15...v3.1.16) (2023-10-24)


### ✍ Chore

* **deps:** bump urllib3 from 2.0.6 to 2.0.7 ([2b96a25](https://github.com/dangeroustech/StreamDL/commit/2b96a254fad16e91961be25b0a663f3bafda8388))

### [3.1.15](https://github.com/dangeroustech/StreamDL/compare/v3.1.14...v3.1.15) (2023-10-17)

### [3.1.14](https://github.com/dangeroustech/StreamDL/compare/v3.1.13...v3.1.14) (2023-10-17)


### ✍ Chore

* update actions deps ([84a7481](https://github.com/dangeroustech/StreamDL/commit/84a748131b86a23ae724b4f51c9b65c5053d5fd2))

### [3.1.13](https://github.com/dangeroustech/StreamDL/compare/v3.1.12...v3.1.13) (2023-10-17)


### ✍ Chore

* **deps-dev:** bump gitpython from 3.1.36 to 3.1.37 ([ae447fe](https://github.com/dangeroustech/StreamDL/commit/ae447fed974a7fa71174c4ae51ba8ff646536e69))
* **deps:** bump golang.org/x/net from 0.8.0 to 0.17.0 ([787478f](https://github.com/dangeroustech/StreamDL/commit/787478f885961be34937446b2cf8f026b05c1643))

### [3.1.12](https://github.com/dangeroustech/StreamDL/compare/v3.1.11...v3.1.12) (2023-10-04)


### ✍ Chore

* **deps:** bump urllib3 from 2.0.4 to 2.0.6 ([13dbac5](https://github.com/dangeroustech/StreamDL/commit/13dbac50b403e2933ada5a9fc5a655659df5efc5))

### [3.1.11](https://github.com/dangeroustech/StreamDL/compare/v3.1.10...v3.1.11) (2023-09-12)


### ✍ Chore

* add todo ([663db81](https://github.com/dangeroustech/StreamDL/commit/663db81248984c46cba86fdb05cbdbef20cf139e))
* bump poetry version to 1.6.1 ([c3ba4d2](https://github.com/dangeroustech/StreamDL/commit/c3ba4d2301daac2b27f6dd5ca7616230870d60a2))
* rename test to be twitch specific ([a66bcda](https://github.com/dangeroustech/StreamDL/commit/a66bcda8e93f85497e8be9e28062f54023a33566))
* update to new ubuntu and python versions ([7169e8d](https://github.com/dangeroustech/StreamDL/commit/7169e8dce335e0aa1eaca356981d3c2238557a28))


### 📚 Documentation

* fix indentation ([cb67e7c](https://github.com/dangeroustech/StreamDL/commit/cb67e7c43b45aafe20cb7a87a9b7909541db40b8))
* update wording around default log level ([5481c39](https://github.com/dangeroustech/StreamDL/commit/5481c39291a89216fd2789715aa9f712a4e75666))


### 🤖 CI/CD

* add docker buildx setup to support caching ([9250619](https://github.com/dangeroustech/StreamDL/commit/925061957f1969e2cfad534100feb14a6d2c162f))
* add explicit run step ([45429f2](https://github.com/dangeroustech/StreamDL/commit/45429f2d2c51efaa8176e50c7ac7e1ca1a27a725))
* add golang testing stage ([8c23f39](https://github.com/dangeroustech/StreamDL/commit/8c23f3962a2416b55b66f656dfb31163835510bf))
* add local server build to test workflow ([af037b8](https://github.com/dangeroustech/StreamDL/commit/af037b883f304988106a0dd8a8c468159de75a51))
* pass env var as a string ([bc3a508](https://github.com/dangeroustech/StreamDL/commit/bc3a5087418500260ca70f50b05303b36e6e287e))
* run docker action inline and background ([4ee4148](https://github.com/dangeroustech/StreamDL/commit/4ee4148e2229c001af8effbaad8abcb9f638d0b2))


### 🐛 Bug Fixes

* correct logging ([919c4ed](https://github.com/dangeroustech/StreamDL/commit/919c4ed0d72d3193ac545300554250b239109e21))
* properly raise errors for PluginNotFound ([faef870](https://github.com/dangeroustech/StreamDL/commit/faef8705434bd757b3f6ba9bcf9e83422203197e))
* test: correct python version ([02bb7f9](https://github.com/dangeroustech/StreamDL/commit/02bb7f901b2bd1e2bf81412cbcc1d05091ce1ecb))
* test: directly run the python? ([07353e2](https://github.com/dangeroustech/StreamDL/commit/07353e2b2c71cbc5c0f904508a64d693118f6016))
* test: install deps ([b56d21e](https://github.com/dangeroustech/StreamDL/commit/b56d21eb95581baf868218c7bf75336d2930a9b5))
* test: typo ([b9ce052](https://github.com/dangeroustech/StreamDL/commit/b9ce0520a57fba7eee3201033dc4f7a4d96f0a2e))


### 🧪 Tests

* actually remember how poetry is used ([bcc4ae7](https://github.com/dangeroustech/StreamDL/commit/bcc4ae7af826f6781a2d0f554de3e4e376d242b3))
* add 404 client test ([de568bd](https://github.com/dangeroustech/StreamDL/commit/de568bd1256aaffa64a5d4bc4f0885002620ce97))
* add comments ([5a2d7c7](https://github.com/dangeroustech/StreamDL/commit/5a2d7c7405547bbd5eda80456ad65f28d1d28a4f))
* add tests for more sites ([ff595a4](https://github.com/dangeroustech/StreamDL/commit/ff595a43b699e85564dbf8c77aa713d1b4c1173c))
* fully deprecate test pid killer ([9f9461e](https://github.com/dangeroustech/StreamDL/commit/9f9461e7a95dc7ac0391faf8fefd242014fd7fe3))
* just run the server inline ([a3e368d](https://github.com/dangeroustech/StreamDL/commit/a3e368d5f4e80faa5602f1a8eb29d883e805c9d6))
* manually govern killing the server ([7de5171](https://github.com/dangeroustech/StreamDL/commit/7de51718d7f6f7957968e4b5db80f34478eee06c))
* remove pid killing logic ([f3e0d3d](https://github.com/dangeroustech/StreamDL/commit/f3e0d3d21ec917924ef32c40d922671f8247eee7))
* simplify testing strategy ([31a4db0](https://github.com/dangeroustech/StreamDL/commit/31a4db0203beaffa8d4a4181ff9330ecfde7379b))

### [3.1.10](https://github.com/dangeroustech/StreamDL/compare/v3.1.9...v3.1.10) (2023-09-09)


### 🐛 Bug Fixes

* migrate release action away from deprecated ([e1503bf](https://github.com/dangeroustech/StreamDL/commit/e1503bfe174f1c9a69c50aa7bfcc62402ac855a0))
* upgrade actions/setup-python to v4 ([e0d2971](https://github.com/dangeroustech/StreamDL/commit/e0d297149962e77e106114ebced2cb114f812267))
* upgrade checkout and setup-node deps ([5aedd65](https://github.com/dangeroustech/StreamDL/commit/5aedd6511663ab32b8850a911c6db68a62f29aaf))

### [3.1.9](https://github.com/dangeroustech/StreamDL/compare/v3.1.8...v3.1.9) (2023-09-09)


### 🐛 Bug Fixes

* Dockerfile.client to reduce vulnerabilities ([d686d83](https://github.com/dangeroustech/StreamDL/commit/d686d835baf1c58a8e6e5eb742a259a0e7df5429))

### [3.1.8](https://github.com/dangeroustech/StreamDL/compare/v3.1.7...v3.1.8) (2023-09-09)


### ✍ Chore

* **deps-dev:** bump gitpython from 3.1.31 to 3.1.35 ([61dde00](https://github.com/dangeroustech/StreamDL/commit/61dde00fb71c25e2838440f74f479fa4f3b13ca1))

### [3.1.7](https://github.com/dangeroustech/StreamDL/compare/v3.1.6...v3.1.7) (2023-09-09)


### 📚 Documentation

* use local reference for example compose file ([3a4136a](https://github.com/dangeroustech/StreamDL/commit/3a4136aac20f33a8ab65718d097dd8c41f7a64be))


### 🐛 Bug Fixes

* correct log level specification ([590e641](https://github.com/dangeroustech/StreamDL/commit/590e64166e65d1570dcc3915109ddc14a521d2d7))
* correct logging implementation ([485f585](https://github.com/dangeroustech/StreamDL/commit/485f585be59b5dc88bb92637bf7566300839d97a))
* migrate to new streamlink options format ([acb8229](https://github.com/dangeroustech/StreamDL/commit/acb8229cc162d67c443074ba3a5c7660f08edf23))

### [3.1.6](https://github.com/dangeroustech/StreamDL/compare/v3.1.5...v3.1.6) (2023-08-05)


### 🐛 Bug Fixes

* Dockerfile.client to reduce vulnerabilities ([c15f8d9](https://github.com/dangeroustech/StreamDL/commit/c15f8d9357995be4571703c09bdc5a25e719e608))


### ✍ Chore

* **deps:** bump certifi from 2022.12.7 to 2023.7.22 ([b7322cb](https://github.com/dangeroustech/StreamDL/commit/b7322cb0974723dc4add4eb5d6fcab8e50051f14))

### [3.1.5](https://github.com/dangeroustech/StreamDL/compare/v3.1.4...v3.1.5) (2023-05-30)


### 🤖 CI/CD

* allow code scan to fail ([5e8026e](https://github.com/dangeroustech/StreamDL/commit/5e8026ecf04e5dc868e85fdb1f750a64f16aade7))
* switch to building on pull request target ([aac8344](https://github.com/dangeroustech/StreamDL/commit/aac834464ec09de35f995291d01806d0250793ec))


### ✍ Chore

* bump various ci tool versions ([e1dcde8](https://github.com/dangeroustech/StreamDL/commit/e1dcde86c7fa69371514996305c0078637380d55))
* **deps:** bump requests from 2.28.2 to 2.31.0 ([149dd80](https://github.com/dangeroustech/StreamDL/commit/149dd802a7f74a53032787d8136e7f3fd998c517))

### [3.1.4](https://github.com/dangeroustech/StreamDL/compare/v3.1.3...v3.1.4) (2023-04-30)


### ✍ Chore

* **deps:** bump google.golang.org/protobuf from 1.29.0 to 1.29.1 ([48570b5](https://github.com/dangeroustech/StreamDL/commit/48570b521e450a91661801ad4022c6ad899ea697))
* update docker login-action to v2 ([80ccd32](https://github.com/dangeroustech/StreamDL/commit/80ccd32dd3df070135ab4e902465371889dc93aa))

### [3.1.3](https://github.com/dangeroustech/StreamDL/compare/v3.1.2...v3.1.3) (2023-03-09)


### 🧪 Tests

* fix: yaml formatting ([37396dd](https://github.com/dangeroustech/StreamDL/commit/37396dd845376bbc2c637844270e99affbc9905d))
* update pr tests ([dd5caa6](https://github.com/dangeroustech/StreamDL/commit/dd5caa6b2a7b8719cfc518d03d758bb480d9d06e))


### 🐛 Bug Fixes

* cannot push and load because reasons ([1fc974c](https://github.com/dangeroustech/StreamDL/commit/1fc974c5aabef2191b5f9688008da821b135dd50))
* go deps update ([c41e54b](https://github.com/dangeroustech/StreamDL/commit/c41e54b56af238a54ee78fb5a554b6843483777a))
* testing manual pprof import ([bc98995](https://github.com/dangeroustech/StreamDL/commit/bc989956295d432c894fdcbb4f3d817327797f0c))
* version pin golang properly ([d4ac670](https://github.com/dangeroustech/StreamDL/commit/d4ac6702ca22835b5f5fb7ee8325230570ab1a99))


### 🤖 CI/CD

* build on issue* PRs ([3fee9cc](https://github.com/dangeroustech/StreamDL/commit/3fee9cc3ea041943bff39fba9a76a55a2daa4255))
* continue on error if there's no code scanning ([b7fe857](https://github.com/dangeroustech/StreamDL/commit/b7fe857ca7d5e61ed3c88c0574a500bc537ee359))
* deprecate arm64 staging builds ([aea3a1c](https://github.com/dangeroustech/StreamDL/commit/aea3a1cdd35e2e5cddcca1a8f9b5cbe16e31bafd))
* fix: base needs to be staging for PRs ([ad8e96a](https://github.com/dangeroustech/StreamDL/commit/ad8e96a3875bad7b3b3e8d4e00a5a0229fa54a30))
* just work, we'll fix the protobuf thing later ([a5d12eb](https://github.com/dangeroustech/StreamDL/commit/a5d12eb2d7fb8403a055c4b7410cb5dd8f936f37))
* load doesn't load... ([6350937](https://github.com/dangeroustech/StreamDL/commit/6350937eaf335e90f6779398ec197c7b6ad461b6))
* remove org flag from local image ([cd050b2](https://github.com/dangeroustech/StreamDL/commit/cd050b26d75247b35b3d0e5b6b277e8abf82e999))

### [3.1.2](https://github.com/dangeroustech/StreamDL/compare/v3.1.1...v3.1.2) (2023-03-09)


### ✍ Chore

* add build-essentials to container ([2d6c7cd](https://github.com/dangeroustech/StreamDL/commit/2d6c7cd9171c9a58df81f739223a5df12e99ab3e))
* bump poetry version in Dockerfile ([ebcfe66](https://github.com/dangeroustech/StreamDL/commit/ebcfe668ad3b7d687872f42c9a3ae7c56818d6d0))
* **deps:** bump certifi from 2022.9.24 to 2022.12.7 ([faf1d22](https://github.com/dangeroustech/StreamDL/commit/faf1d22eb49bd8b24796504be2941412c3bb662b))
* **deps:** bump golang.org/x/net from 0.1.0 to 0.7.0 ([d61d5af](https://github.com/dangeroustech/StreamDL/commit/d61d5afbf0e3267e1d02bea3ac5f30c2d273db6d))
* **deps:** bump golang.org/x/net from 0.1.0 to 0.7.0 ([743f4ad](https://github.com/dangeroustech/StreamDL/commit/743f4adf8876e185c6c134b551ded7038d802ef5))
* **deps:** bump setuptools from 65.3.0 to 65.5.1 ([ca44107](https://github.com/dangeroustech/StreamDL/commit/ca44107ae72b6dc133a0c7cc53fdb3b7c4b7c621))
* fully roll back ffmpeg ([0fe3828](https://github.com/dangeroustech/StreamDL/commit/0fe3828663cd1b002b6e909ded4a29517c5d6856))
* roll back to python 3.10 ([de7fa61](https://github.com/dangeroustech/StreamDL/commit/de7fa61d38bf400b28529734a7d7718b6ddcafe9))
* slightly roll ffmpeg back ([da9b408](https://github.com/dangeroustech/StreamDL/commit/da9b408fbec96a5d3d9c878794a878345821eb1b))
* update .gitignore ([d6d9d8f](https://github.com/dangeroustech/StreamDL/commit/d6d9d8f167e5f894ff065c11436ac8370cc6962a))
* update docker underlying OS ([e73cae3](https://github.com/dangeroustech/StreamDL/commit/e73cae38d64e1f25eb395759437a049fd4bb1c82))
* update ffmpeg version ([fa440c8](https://github.com/dangeroustech/StreamDL/commit/fa440c8b2d799277735161d6dd527f2458507a48))
* update poetry deps ([0869e05](https://github.com/dangeroustech/StreamDL/commit/0869e0525fc897f3691f6bbef27a8068a1b1c2c5))
* upgrade pip ([9fec876](https://github.com/dangeroustech/StreamDL/commit/9fec876e2d1565277092847bec7f453b72fd2378))


### 🐛 Bug Fixes

* better version pinning for golang ([b58850f](https://github.com/dangeroustech/StreamDL/commit/b58850f1f3df7237f00ced0ba956f5eaf7f7970e))
* combine file copies into one layer ([81fd0d2](https://github.com/dangeroustech/StreamDL/commit/81fd0d2345f0a032b93b5963048188e7e3842302))
* hippy hop ([35ddf18](https://github.com/dangeroustech/StreamDL/commit/35ddf18d9d85f4ad316776bccb8200a24dc034e9))
* idk rewind ([8d3cdb1](https://github.com/dangeroustech/StreamDL/commit/8d3cdb14a25a287ca6a0bd9ffd96bf4459810cc8))
* install build-essential ([b42a27b](https://github.com/dangeroustech/StreamDL/commit/b42a27ba365702d51603cac0726ea25c4bfe0b1d))
* pip upgrade breaks things ([40cd5d3](https://github.com/dangeroustech/StreamDL/commit/40cd5d3c1a4e3b813fa5ef2fdc8c534513ca16ce))
* revert ([dc28c5a](https://github.com/dangeroustech/StreamDL/commit/dc28c5a7ab6d223f341436ddeb592f6c4d8d4a18))
* see if adding wheel speeds up build time ([9212df7](https://github.com/dangeroustech/StreamDL/commit/9212df72c6a52f6a43742cd203c7852fe32547b9))
* thicc python ([4201767](https://github.com/dangeroustech/StreamDL/commit/4201767e163ae8186afde31449e2c58e28baed86))
* this builds locally... ([a9a6704](https://github.com/dangeroustech/StreamDL/commit/a9a6704ae752b35bfd0a2a793bf08e4eccee9e6c))
* update go mod ([f9fe66c](https://github.com/dangeroustech/StreamDL/commit/f9fe66c2d118208b2c6571b81b7e88e63b28604e))

### [3.1.1](https://github.com/dangeroustech/StreamDL/compare/v3.1.0...v3.1.1) (2022-10-30)


### 🐛 Bug Fixes

* bump debian version for less vulns ([9b3491b](https://github.com/dangeroustech/StreamDL/commit/9b3491b9c4adc35d1c359a2997fd19946f194137))
* remove vulnerable go1.16 deps ([50e0dbe](https://github.com/dangeroustech/StreamDL/commit/50e0dbe1f1b05b314d883d0a159928148355569f))
* specific staging tag for staging scan ([b131dfe](https://github.com/dangeroustech/StreamDL/commit/b131dfe79332302f6389f9813309ec0fe2907c4e))


### 🤖 CI/CD

* add Snyk scan to master CI ([13f8e7b](https://github.com/dangeroustech/StreamDL/commit/13f8e7be2b9ac6fa52caddb42f1c9cb381ff7dbf))

## [3.1.0](https://github.com/dangeroustech/StreamDL/compare/v3.0.4...v3.1.0) (2022-10-30)


### 🎉 New Features

* sec: add snyk checks to staging ([1ff4e9d](https://github.com/dangeroustech/StreamDL/commit/1ff4e9d64f4ff82b805b826174a701ba4695d6e1))

### [3.0.4](https://github.com/dangeroustech/StreamDL/compare/v3.0.3...v3.0.4) (2022-10-30)

### [3.0.3](https://github.com/dangeroustech/StreamDL/compare/v3.0.2...v3.0.3) (2022-10-09)


### 🐛 Bug Fixes

* no longer using python for client operations ([cdd4da0](https://github.com/dangeroustech/StreamDL/commit/cdd4da06bd394270bfeabcb9fac13c241f902099))
* regen protoc files for protobuf v4 bump ([fd0b282](https://github.com/dangeroustech/StreamDL/commit/fd0b2823fb9f837ca8e69aa974ccbdb311d03487))
* remove --twitch-disable-hosting usage ([7b13fc7](https://github.com/dangeroustech/StreamDL/commit/7b13fc77c9a59579830ca89a24131887fc1f2f55))
* use latest image version in example compose ([b95d1a3](https://github.com/dangeroustech/StreamDL/commit/b95d1a3f2e44177f98bff8aaa6df81ce863c8259))


### ✍ Chore

* fix linting issue ([ee1f607](https://github.com/dangeroustech/StreamDL/commit/ee1f607e0280ee0f58f20cbe58994470ca106b80))
* poetry update ([0b0b330](https://github.com/dangeroustech/StreamDL/commit/0b0b3309fd95646ee3ee71a1d842dc5c9b0f9113))

### [3.0.2](https://github.com/dangeroustech/StreamDL/compare/v3.0.1...v3.0.2) (2022-10-09)


### ✍ Chore

* **deps:** bump protobuf from 3.20.1 to 3.20.2 ([76d2a9d](https://github.com/dangeroustech/StreamDL/commit/76d2a9d26e468db3d8417ce703e75914451a0747))

### [3.0.1](https://github.com/dangeroustech/StreamDL/compare/v3.0.0...v3.0.1) (2022-08-19)


### ✍ Chore

* cleanup deps ([9c679d3](https://github.com/dangeroustech/StreamDL/commit/9c679d3e0ff84c8aa784476720767ec528d54e39))
* deps update ([e5afde3](https://github.com/dangeroustech/StreamDL/commit/e5afde3eda4d739ba63613fc59eafb696b6b31cd))
* file cleanup ([73ef694](https://github.com/dangeroustech/StreamDL/commit/73ef694522cce9802d42bb3e5beaff6b7ef328b5))


### 🐛 Bug Fixes

* correct default tick_time ([924fcb1](https://github.com/dangeroustech/StreamDL/commit/924fcb184fa81ad3a64a3aceb221161302246d29))
* properly parse log_level from env ([650bbdd](https://github.com/dangeroustech/StreamDL/commit/650bbdd3119f99f84823243180125ff0b5a9d1ac))
* update ci to publish fixes ([5de7e6e](https://github.com/dangeroustech/StreamDL/commit/5de7e6e8083df3bfd8cb385721a07c5c3c9c2645))


### 📚 Documentation

* :memo: correct docs around tick_time ([a9d4802](https://github.com/dangeroustech/StreamDL/commit/a9d4802f92788e877f63bd3efb6a2be5b6442acc))
* update badges ([ea8f168](https://github.com/dangeroustech/StreamDL/commit/ea8f1686c66dbef03118743ec9f9a987a840c16c))
* update SECURITY.md ([4a5ab25](https://github.com/dangeroustech/StreamDL/commit/4a5ab25f4dcb642b084d43d40e237ec485926ac8))

## [3.0.0](https://github.com/dangeroustech/StreamDL/compare/v2.3.0...v3.0.0) (2022-08-18)


### ⚠ BREAKING CHANGES

* v3 publication :tada:

### 📚 Documentation

* :sparkles: update docs for v3 ([056eede](https://github.com/dangeroustech/StreamDL/commit/056eede02441d9fa114833af1e33bd3b7db47e36))

## [2.3.0](https://github.com/dangeroustech/StreamDL/compare/v2.2.1...v2.3.0) (2022-08-18)


### 🔥 Style

* plans for refactor ([34e7b80](https://github.com/dangeroustech/StreamDL/commit/34e7b80a84afddb87360915ef443ff2f7dbaf4a0))


### 🎉 New Features

* add proper logging ([139054b](https://github.com/dangeroustech/StreamDL/commit/139054b60850768bdda80b146e5f43f582fc130e))
* add relevant flags ([3da9c2f](https://github.com/dangeroustech/StreamDL/commit/3da9c2f0921d8775538abd43096ffa11898ca486))
* **app:** add protobuf server implementation ([70d0c1b](https://github.com/dangeroustech/StreamDL/commit/70d0c1b3e2fac129e7b754ee14691bc2cf35dbe4))
* **app:** WIP - golang grpc client implementation ([2f2c046](https://github.com/dangeroustech/StreamDL/commit/2f2c0462f008f5aeaa5e62603c404de64fc067f5))
* initial ffmpeg download ([e2d0211](https://github.com/dangeroustech/StreamDL/commit/e2d0211854ce017ad57a868a4fe6591ed622cce8))
* yaml parsing ([47fd5ec](https://github.com/dangeroustech/StreamDL/commit/47fd5ec41224969a1155fab2044b13fee81c80fa))


### ✍ Chore

* add error conditions ([78248cb](https://github.com/dangeroustech/StreamDL/commit/78248cbb7dfc1df25342a95a3260be9737f4a3ed))
* add some logging ([c4ffd88](https://github.com/dangeroustech/StreamDL/commit/c4ffd888db36776dc6377b6e265d585cf789a764))
* better logging ([8b56aa1](https://github.com/dangeroustech/StreamDL/commit/8b56aa12bde0d7a4b07a33bd8a7a7c59bcb6c2e4))
* bump poetry deps ([fb34276](https://github.com/dangeroustech/StreamDL/commit/fb3427678e2578fe23932c9070f9e8528172a14c))
* bump python version for pattern matching ([432a6f8](https://github.com/dangeroustech/StreamDL/commit/432a6f85a7ea7594226a5589046cfc1bc1981e81))
* bump yaml version ([4581d1b](https://github.com/dangeroustech/StreamDL/commit/4581d1bbe65ff1a2dd7d95209386c5ece9462c78))
* bump yaml version to v3 ([e56ccbf](https://github.com/dangeroustech/StreamDL/commit/e56ccbf8974ef048e2460eafc327a54c7b9505f3))
* log type changes ([8792099](https://github.com/dangeroustech/StreamDL/commit/879209978fb09ae6e45c32dbab466e944599cfe3))
* reorganise functions ([591735f](https://github.com/dangeroustech/StreamDL/commit/591735f4c9d0228b022f5a42971be07f8d5d7d45))
* sensible file naming ([c124efa](https://github.com/dangeroustech/StreamDL/commit/c124efa6f5c285ec4217d5e0834d55e0d96c1314))
* upgrade yaml package version ([f4d93c5](https://github.com/dangeroustech/StreamDL/commit/f4d93c5fec4bc66d6a62c60ea85c1d620dffeddf))


### 🐛 Bug Fixes

* add 200 code on success ([5469931](https://github.com/dangeroustech/StreamDL/commit/54699316b7651219a8514f88bd0c755989cafa77))
* correct deprecated option ([8fae1a1](https://github.com/dangeroustech/StreamDL/commit/8fae1a161d60f56f6cfcb3cdf03367dbc384874b))
* correct error flow ([8ae0997](https://github.com/dangeroustech/StreamDL/commit/8ae0997dfbe9ce0bcd3db3e12c0212b77911f418))
* correct example mappings ([5efc7e6](https://github.com/dangeroustech/StreamDL/commit/5efc7e6e965da092464ad1f34bf250e3be833a12))
* correct example yaml keys ([1173aac](https://github.com/dangeroustech/StreamDL/commit/1173aac4e0340f04cbf19436732a180ca28d8ee6))
* every condition besides ctrl c works fine... ([17b45a5](https://github.com/dangeroustech/StreamDL/commit/17b45a5bb46076f2114e8fa254a988f5f4016ed9))
* minor docker retooling ([e82a902](https://github.com/dangeroustech/StreamDL/commit/e82a902c4621d3c7a6bf271ee95432a6188e8432))
* proper gRPC error handling ([952b945](https://github.com/dangeroustech/StreamDL/commit/952b9456d9fdc6849072504270fa2e5032d7a30a))
* pull grpc socket stuff from env ([1800481](https://github.com/dangeroustech/StreamDL/commit/1800481738fde5dd575d8ee3ca93b690feb963bf))
* rename entrypoint scripts ([8d6b460](https://github.com/dangeroustech/StreamDL/commit/8d6b460f1e3a8c6063a9a34d46534a5c0e866335))
* sensible yaml keys ([5df3907](https://github.com/dangeroustech/StreamDL/commit/5df39077164f758153f3a84b2aa2655765a7b23b))
* tidied up docker build ([58f23ef](https://github.com/dangeroustech/StreamDL/commit/58f23ef39aa4b35f5679e60c85a0e4c8a7fd70ea))


### 📚 Documentation

* correct example to pull from dockerhub ([ed028b3](https://github.com/dangeroustech/StreamDL/commit/ed028b369c93800e8f8e5ab5d394b1628bbdb007))
* remove old example dockerfile ([a09ed95](https://github.com/dangeroustech/StreamDL/commit/a09ed95bb2b1b3038383966acc20fcd2f92a1509))
* update example config file ([928116e](https://github.com/dangeroustech/StreamDL/commit/928116ee740cd473e43d5d7b944a48f5027aa2b3))
* update example docker-compose ([53a700f](https://github.com/dangeroustech/StreamDL/commit/53a700f892136b8d33da8d70f44a4ac6046fdf5c))


### 🧪 Tests

* correct file name ([25834cc](https://github.com/dangeroustech/StreamDL/commit/25834cccb26680f4e4e1d984f7ed22b28d3ff18a))
* deprecate python 3.9 ([46b04a0](https://github.com/dangeroustech/StreamDL/commit/46b04a04a8a493ad892249a2ff3b449a9892f35b))
* testing changes ([644e4d0](https://github.com/dangeroustech/StreamDL/commit/644e4d09f87ffac6c89d28f8cf7d6c2f375656d7))


### 🤖 CI/CD

* fix dockerhub typos ([097a5ed](https://github.com/dangeroustech/StreamDL/commit/097a5ed91030e273e72046d6a5c74ff81d58d40c))
* update ci jobs for multi container builds ([d9da9e2](https://github.com/dangeroustech/StreamDL/commit/d9da9e2dea00eba3411b621ad84894d9caceba26))

### [2.2.1](https://github.com/dangeroustech/StreamDL/compare/v2.2.0...v2.2.1) (2022-03-10)


### ✍ Chore

* deps update ([dbb63a1](https://github.com/dangeroustech/StreamDL/commit/dbb63a166435baf7f823479c6211053057a73467))

## [2.2.0](https://github.com/dangeroustech/StreamDL/compare/v2.1.1...v2.2.0) (2022-01-29)


### ✍ Chore

* **app:** import cleaning ([a8cf8be](https://github.com/dangeroustech/StreamDL/commit/a8cf8be82d30ab456990ba43b52fde5623c088ce))
* **deps:** update deps ([d717a6b](https://github.com/dangeroustech/StreamDL/commit/d717a6b0fffdd8fab8eee894471dd01f772958d8))


### 🎉 New Features

* **app:** allow custom ytdl options specification ([bffe8d4](https://github.com/dangeroustech/StreamDL/commit/bffe8d4f4fa06e6beb4ff8c5134ab9605d70c036))


### 🧪 Tests

* **app:** fix broken offline twitch test ([5c82a21](https://github.com/dangeroustech/StreamDL/commit/5c82a2150df8d537ab68d49798ed4e78a1efffb6))

### [2.1.1](https://github.com/dangeroustech/StreamDL/compare/v2.1.0...v2.1.1) (2022-01-29)


### 🐛 Bug Fixes

* **ci:** correct repo checkout for tags ([0dda40b](https://github.com/dangeroustech/StreamDL/commit/0dda40ba7281c1785ef63a13eea9d5a57f4feffd))

## [2.1.0](https://github.com/dangeroustech/StreamDL/compare/v2.0.5...v2.1.0) (2022-01-29)


### 🎉 New Features

* **build:** slim down docker conatiners ([5232609](https://github.com/dangeroustech/StreamDL/commit/5232609d91b639bdd8afbaa9a3fb1777203aa46d)), closes [#219](https://github.com/dangeroustech/StreamDL/issues/219)


### 🐛 Bug Fixes

* **app:** use ffmpeg copy codec ([c4c694a](https://github.com/dangeroustech/StreamDL/commit/c4c694a71088bd2d8aea625e5879613df721c07b))
* **build:** supporting python call without poetry ([2acb76b](https://github.com/dangeroustech/StreamDL/commit/2acb76b266461d077b16af620842123b5cf41183))

### [2.0.5](https://github.com/dangeroustech/StreamDL/compare/v2.0.4...v2.0.5) (2022-01-29)


### ✍ Chore

* add security vuln issue template ([c191016](https://github.com/dangeroustech/StreamDL/commit/c1910166d83f1deefce33e09d1cb0348bc16c5e9))
* clarity around bug template ([cde4b44](https://github.com/dangeroustech/StreamDL/commit/cde4b447ba7ae28a475163ed9ff318338f062ecf))
* update contributing.md ([eb2596d](https://github.com/dangeroustech/StreamDL/commit/eb2596dd5d8b285c85813a666214aba3d7b6ce00))
* update supported versions ([819c6b7](https://github.com/dangeroustech/StreamDL/commit/819c6b70e08036ee19f08f43b822c3600f6aa6ad))

### [2.0.4](https://github.com/dangeroustech/StreamDL/compare/v2.0.3...v2.0.4) (2022-01-29)


### 🤖 CI/CD

* reduce codeql frequency ([9052ab7](https://github.com/dangeroustech/StreamDL/commit/9052ab7345056d5d8effbc000445773468866f07))


### 🐛 Bug Fixes

* **changelog:** add changelog config ([dc5df47](https://github.com/dangeroustech/StreamDL/commit/dc5df4715cc60f6c269ffe8e5b58b58368de4a96))
* install changelog npm package ([ae16b56](https://github.com/dangeroustech/StreamDL/commit/ae16b56227795dfb1b7ef1065317e6f4f764f749))

### [2.0.3](https://github.com/dangeroustech/StreamDL/compare/v2.0.2...v2.0.3) (2022-01-29)


### 🐛 Bug Fixes

* remove unnecessary docker build ([a331f56](https://github.com/dangeroustech/StreamDL/commit/a331f569702a1403f04602d128d81db025af05d9))

### [2.0.2](https://github.com/dangeroustech/StreamDL/compare/v0.1.0...v2.0.2) (2022-01-29)


### ✍ Chore

* proper version bump ([f62706a](https://github.com/dangeroustech/StreamDL/commit/f62706a024fda5ef3c34d7a8ab6efc3f7928b193))


### 🐛 Bug Fixes

* properly order release stuff ([123b00e](https://github.com/dangeroustech/StreamDL/commit/123b00ed5480b20e4bd8b3afc54f83213d832692))
* revert and fix changelog options ([6f2545d](https://github.com/dangeroustech/StreamDL/commit/6f2545d93092458e7a851fe3bdbe7bd84d4c0e14))

## [0.1.0](https://github.com/dangeroustech/StreamDL/compare/v2.0.1...v0.1.0) (2022-01-29)


### 🔥 Style

* first actual run through black ([e023416](https://github.com/dangeroustech/StreamDL/commit/e0234160f3f11b9d4c3b3908d942587a74bbdbdc))
* less lines [skip ci] ([9191e46](https://github.com/dangeroustech/StreamDL/commit/9191e465ef8aace5ed1203fd6aa9fc9e9d5fe848))


### 🏭 Build

* differentiate names [skip ci] ([8fe78f5](https://github.com/dangeroustech/StreamDL/commit/8fe78f5c24b863ad0a7c7f1e39ee40c1db446422))
* split build workflows ([e138f6c](https://github.com/dangeroustech/StreamDL/commit/e138f6c8b96ccd04eebde2c0e88ac81eefa47f9c))
* update dockerfile reference ([03e6fa3](https://github.com/dangeroustech/StreamDL/commit/03e6fa30d2e94718f1479069ab945e5d77b3e9db))


### 🧪 Tests

* correctly import yt-dlp utils ([40cfe57](https://github.com/dangeroustech/StreamDL/commit/40cfe57cb559b4476cc00d4a9622b06b6071ce10))


### 📚 Documentation

* document new -q flag ([8bb36fe](https://github.com/dangeroustech/StreamDL/commit/8bb36fe6e93b7f3b841675839ecd174575e8c530))
* remove old changelog ([d63ace6](https://github.com/dangeroustech/StreamDL/commit/d63ace6550125b87051b7b64e52ed9030a000c85))


### 🐛 Bug Fixes

* add black as dev package for linting ([0408155](https://github.com/dangeroustech/StreamDL/commit/0408155f1481ea33778b7902d3ecb9bf10f6c7ab))
* add ffmpeg install to container build ([37fd89a](https://github.com/dangeroustech/StreamDL/commit/37fd89ab4b5f368cbc6890ab732c3c3a1bae0826))
* allow custom quality specification for twitch ([9808629](https://github.com/dangeroustech/StreamDL/commit/9808629b0463806dd271a5c5dfc3d36724f277a6))
* author and version bump ([8ca63d4](https://github.com/dangeroustech/StreamDL/commit/8ca63d440421d10ae0006e294edbb3de92cff504))
* author slug ([8dbbdc8](https://github.com/dangeroustech/StreamDL/commit/8dbbdc87cfafc4be1661c59c84f731f489d63d74))
* coherent example file naming ([31e4730](https://github.com/dangeroustech/StreamDL/commit/31e4730c954a19c45e08431af80af3dddd875054))
* correct SIG* exit code ([72bcfb0](https://github.com/dangeroustech/StreamDL/commit/72bcfb0bc6c8e44f18889691948e9bf466cbc1cb))
* native streamlink/ffmpeg stream downloading ([ed6a036](https://github.com/dangeroustech/StreamDL/commit/ed6a036feb5a93d0bff84473d7c538c96dc4da94)), closes [#212](https://github.com/dangeroustech/StreamDL/issues/212)
* natively creating twitch dir ([5de7a24](https://github.com/dangeroustech/StreamDL/commit/5de7a244bcead97b9972c07bd975a5fa8c19e9f5))
* rename to sensible workflow names ([92dc257](https://github.com/dangeroustech/StreamDL/commit/92dc2575e7979fc92d3b651185536a361d2e4c91))
* shut ffmpeg up ([ea61f70](https://github.com/dangeroustech/StreamDL/commit/ea61f701925548b7a2720b331e24a75baf3dac7c))
* weird offline stream bug ([18b053d](https://github.com/dangeroustech/StreamDL/commit/18b053da4240574a604c1a173c4705d6525d2360))
* yt-dlp dropped in ([d90a8f2](https://github.com/dangeroustech/StreamDL/commit/d90a8f267fff7d00454b92bfe34959ee3a3a3cd8))


### 🤖 CI/CD

* add ci workflow ([f96e834](https://github.com/dangeroustech/StreamDL/commit/f96e8340cd8466113a2e70e91ad5e4a22ad95faf))
* add docker build as test ([39124f4](https://github.com/dangeroustech/StreamDL/commit/39124f4b26d8c4f8aa22b328ee6d9acda23163dc))
* change release action to write changelog ([d42db21](https://github.com/dangeroustech/StreamDL/commit/d42db21c507ddd3cabdea0b1c7badec4b9d97488))
* check out the repo first ([14f01d9](https://github.com/dangeroustech/StreamDL/commit/14f01d9b19068388c1511e0678d8417a4b0c1f79))
* CI on staging - dependabot [skip ci] ([d0b7f3d](https://github.com/dangeroustech/StreamDL/commit/d0b7f3d49d4eb18f4216e09ef2afa9fd44f2bbf0))
* correct test tag ([be6aad4](https://github.com/dangeroustech/StreamDL/commit/be6aad48cef5651ffd8f59397947b7bad9ffacdf))
* don't release on staging ([4ae58f0](https://github.com/dangeroustech/StreamDL/commit/4ae58f0ba76049ab206cf6090c8ec1b633fffe81))
* revert cargo version ([0a22d54](https://github.com/dangeroustech/StreamDL/commit/0a22d541474741b4a292346f4b24176fa4929633))


### 🎉 New Features

* add proper tag to dockerhub push ([373952a](https://github.com/dangeroustech/StreamDL/commit/373952a4e8802b7e5cbbce1391575008df0f24a4))
* deprecate old arm builds ([f0f2b05](https://github.com/dangeroustech/StreamDL/commit/f0f2b051fc9ddbf930f23327759190d9a8990e09))


### ✍ Chore

* add todo ([7525bab](https://github.com/dangeroustech/StreamDL/commit/7525bab7dde4e89e692993aa06cd691f8486bc49))
* bump deps ([f387a3b](https://github.com/dangeroustech/StreamDL/commit/f387a3b77b8221fceb036397225d434d63469623))
* improve debug log ([90f6208](https://github.com/dangeroustech/StreamDL/commit/90f62085a32feb201ecb0e61dcc358921525c25c))
* **release:** v0.1.0 [skip ci] ([c7680e1](https://github.com/dangeroustech/StreamDL/commit/c7680e134b91a094326cde9e38873831af8f4c32))
* streamlink bump to 3.0.3 ([841260c](https://github.com/dangeroustech/StreamDL/commit/841260c2e4d87daf2ded0cd0051d73b12319c9a7))
* update gitignore ([c153deb](https://github.com/dangeroustech/StreamDL/commit/c153deb6d90239b49fcff16d3b8f65dfe5b40911))

### [1.2.7](https://github.com/dangeroustech/StreamDL/compare/v1.2.6...v1.2.7) (2022-01-18)


### 📚 Documentation

* readme ([714963a](https://github.com/dangeroustech/StreamDL/commit/714963a3356280e80d1b60bed034854632f50e56))
* update README ([a2d14d2](https://github.com/dangeroustech/StreamDL/commit/a2d14d2b1f66b1ce806e706264df4e1e3ad47613))


### 🏭 Build

* add arm deps ([d5bfc0e](https://github.com/dangeroustech/StreamDL/commit/d5bfc0e85862147afff6510f43888dc75809f2b1))
* arm dep fix :crossed_fingers: ([ee119cf](https://github.com/dangeroustech/StreamDL/commit/ee119cfa31d28897bb67724b5a38a7f3e7280010))
* version pinning ([04ef59e](https://github.com/dangeroustech/StreamDL/commit/04ef59eb977edbbe445158923383693d82efdc3f))


### 🤖 CI/CD

* actually clone repo ([a09dec5](https://github.com/dangeroustech/StreamDL/commit/a09dec5690a64d790c9416c13c08dc629bfb4bef))
* add staging build push ([f642de3](https://github.com/dangeroustech/StreamDL/commit/f642de34c2725bf297ef4c8e64a0ad1367573684))
* bump build to python 3.10 ([cf5df09](https://github.com/dangeroustech/StreamDL/commit/cf5df093e8153d628cdb818f4353d0433d9f753c))
* bump poetry version ([f2f80f3](https://github.com/dangeroustech/StreamDL/commit/f2f80f3c2053936f3ab967d894357a67e280414b))
* change schedule ([8e6a9a5](https://github.com/dangeroustech/StreamDL/commit/8e6a9a584ead588fd47c8c44e12064be9fca11ca))
* cleanup ([63c4a34](https://github.com/dangeroustech/StreamDL/commit/63c4a34763d21374ba3901891d15822187d9095f))
* cleanup ([f66d8b0](https://github.com/dangeroustech/StreamDL/commit/f66d8b044e47914c815d5ce318390f815782d11c))
* docker step complete ([b189308](https://github.com/dangeroustech/StreamDL/commit/b189308e92eea04c98928c677bc8570dc385b854))
* existing cleanup ([eab9fdb](https://github.com/dangeroustech/StreamDL/commit/eab9fdbe896463eb21b06aee9ad1318a315afb0d))
* fix clone ([167a556](https://github.com/dangeroustech/StreamDL/commit/167a5568ee2c36099de515789fdb35b436fee7c9))
* name tweaks ([69a631a](https://github.com/dangeroustech/StreamDL/commit/69a631a6321a6bc577156962fb42133fb967d2a4))
* no need for a matrix, only one language ([c8ec413](https://github.com/dangeroustech/StreamDL/commit/c8ec4136b4d231b9ba06e52c6559e129301af323))
* only restrict push stage ([6629905](https://github.com/dangeroustech/StreamDL/commit/662990560efea4f8a1b20fd8dfedbf7af5bcf712))
* reduce image size because cryptograph wheel ([5258860](https://github.com/dangeroustech/StreamDL/commit/525886022b9e2ff014ab07dc1130fdec27b88798))
* remove comments ([984beaf](https://github.com/dangeroustech/StreamDL/commit/984beaf6a307ad27b7f430db512f67040f46ab17))
* seriously ([02087a6](https://github.com/dangeroustech/StreamDL/commit/02087a6cb6af1b701f7e930ecc777fdcbc5d22ae))
* split build steps ([fb35570](https://github.com/dangeroustech/StreamDL/commit/fb35570866c5bd8abbb66b74f15b49034dff0e4d))
* tweak prefixes ([9dd878a](https://github.com/dangeroustech/StreamDL/commit/9dd878a28f35fb8121a9a1f3c71fb77799afec25))
* typo fix ([79d792a](https://github.com/dangeroustech/StreamDL/commit/79d792a773202d7a354feb31d8790aa845497da8))
* update codeql ([b23645b](https://github.com/dangeroustech/StreamDL/commit/b23645b0b66a05c2629e798f35492bf8c9fe2724))
* workflow replicated ([5dbbc38](https://github.com/dangeroustech/StreamDL/commit/5dbbc3823ca87477c1cb7dde3ebf27700cec9a3d))


### 🔥 Style

* add .editorconfig ([5c32e44](https://github.com/dangeroustech/StreamDL/commit/5c32e440f799433ebe9a98128cb648c8bbd67c3a))
* fix yaml ([041b872](https://github.com/dangeroustech/StreamDL/commit/041b87201f05d99519f3f3c3b8aa7112a2b5737b))
* reordering because pentantry ([98217a4](https://github.com/dangeroustech/StreamDL/commit/98217a48fc001c481b85aef345d06c33cd93d97f))
* syntax ([be1d365](https://github.com/dangeroustech/StreamDL/commit/be1d3651e037a2500a0649ba938b162b4097b685))


### ✍ Chore

* add local ignore files ([a0c6e24](https://github.com/dangeroustech/StreamDL/commit/a0c6e24ce510009b23be6ba2f161417c1a1d803d))
* **deps-dev:** bump pylint from 2.9.6 to 2.10.2 ([3d9f7e9](https://github.com/dangeroustech/StreamDL/commit/3d9f7e94ac1a494bc09d2a072ffe038d79318538))
* **deps-dev:** bump pytest from 6.2.4 to 6.2.5 ([1a2fc96](https://github.com/dangeroustech/StreamDL/commit/1a2fc9693032756b0f32f95f516d9fd8cb944248))
* **deps:** bump streamlink from 2.2.0 to 2.4.0 ([420cf9e](https://github.com/dangeroustech/StreamDL/commit/420cf9ea6cf17dfd39f5b7fee7ef536e468a7ec1))
* update readme and badge name ([8ff2cb7](https://github.com/dangeroustech/StreamDL/commit/8ff2cb77221242e032b44a9f4358a34f469978fe))


### 🐛 Bug Fixes

* add versioning to CI ([d7037a0](https://github.com/dangeroustech/StreamDL/commit/d7037a08aa4a960463f529ca9dd3e049665a5536))
* ci: correct push 'if' ([4b38d3f](https://github.com/dangeroustech/StreamDL/commit/4b38d3fd1922420848701c88f0db560d1b5a84f9))
* update deps and bump to python 3.9 ([c6140a7](https://github.com/dangeroustech/StreamDL/commit/c6140a77828bc98e748f029f82a0d87051616a8a))
* whoops ([8e9509d](https://github.com/dangeroustech/StreamDL/commit/8e9509d7414792a0a649c5dc87ee6773554ddd51))

### [1.2.4](https://github.com/dangeroustech/StreamDL/compare/v1.2.3...v1.2.4) (2020-04-16)

### [1.2.1](https://github.com/dangeroustech/StreamDL/compare/v1.2.0...v1.2.1) (2019-11-07)

## [1.1.0](https://github.com/dangeroustech/StreamDL/compare/v1.0.0...v1.1.0) (2019-10-23)

