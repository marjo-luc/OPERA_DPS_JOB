cwlVersion: v1.2
$graph:
- class: Workflow
  label: operawatermask1
  doc: None
  id: operawatermask1
  inputs:
    SHORT_NAME:
      doc: SHORT_NAME
      label: SHORT_NAME
      type: string
    TEMPORAL:
      doc: TEMPORAL
      label: TEMPORAL
      type: string
    BBOX:
      doc: BBOX
      label: BBOX
      type: string
    LIMIT:
      doc: LIMIT
      label: LIMIT
      type: string
    GRANULE_UR:
      doc: GRANULE_UR
      label: GRANULE_UR
      type: string
    IDX_WINDOW:
      doc: IDX_WINDOW
      label: IDX_WINDOW
      type: string
    S3_URL:
      doc: S3_URL
      label: S3_URL
      type: string
  outputs:
    out:
      type: Directory
      outputSource: process/outputs_result
  steps:
    process:
      run: '#main'
      in:
        SHORT_NAME: SHORT_NAME
        TEMPORAL: TEMPORAL
        BBOX: BBOX
        LIMIT: LIMIT
        GRANULE_UR: GRANULE_UR
        IDX_WINDOW: IDX_WINDOW
        S3_URL: S3_URL
      out:
      - outputs_result
- class: CommandLineTool
  id: main
  requirements:
    DockerRequirement:
      dockerPull: ghcr.io/marjo-luc/opera_dps_job:main
    NetworkAccess:
      networkAccess: true
    ResourceRequirement:
      ramMin: 5
      coresMin: 1
      outdirMax: 20
  baseCommand: /OPERA_DPS_JOB/run.sh
  inputs:
    SHORT_NAME:
      type: string
      inputBinding:
        position: 1
        prefix: --SHORT_NAME
    TEMPORAL:
      type: string
      inputBinding:
        position: 2
        prefix: --TEMPORAL
    BBOX:
      type: string
      inputBinding:
        position: 3
        prefix: --BBOX
    LIMIT:
      type: string
      inputBinding:
        position: 4
        prefix: --LIMIT
    GRANULE_UR:
      type: string
      inputBinding:
        position: 5
        prefix: --GRANULE_UR
    IDX_WINDOW:
      type: string
      inputBinding:
        position: 6
        prefix: --IDX_WINDOW
    S3_URL:
      type: string
      inputBinding:
        position: 7
        prefix: --S3_URL
  outputs:
    outputs_result:
      outputBinding:
        glob: ./output*
      type: Directory
s:author:
- class: s:Person
  s:name: None
s:contributor:
- class: s:Person
  s:name: None
s:citation: null
s:codeRepository: https://github.com/marjo-luc/OPERA_DPS_JOB.git
s:commitHash: 3182b8b354ed38061d06ce0b9d1abe9b9adf2a70
s:dateCreated: 2025-12-05
s:license: https://github.com/marjo-luc/OPERA_DPS_JOB/blob/feat-v1/LICENSE
s:softwareVersion: 1.0.0
s:version: 0.1.1
s:releaseNotes: None
s:keywords: null
$namespaces:
  s: https://schema.org/
$schemas:
- https://raw.githubusercontent.com/schemaorg/schemaorg/refs/heads/main/data/releases/9.0/schemaorg-current-http.rdf
