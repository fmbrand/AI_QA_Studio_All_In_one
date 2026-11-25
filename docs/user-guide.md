# User guide (Phases 1–2)

## Account

1. Open the app and choose **Create an account**. Passwords need at least 10 characters.
2. You stay signed in for up to 14 days on that browser. **Settings** lets you change your name, password (signs out every device) and theme (light, dark or system).
3. Ten wrong passwords in a row lock the account for 15 minutes.

## Projects

- **Projects → New project**: name and platform are required; add type, business domain, application URL, technology stack and description. You become the project's **Owner**.
- The project switcher at the top of the sidebar jumps between your projects.
- **Archive** (Admin or Owner, in project Settings) makes a project read-only and moves it to the Archived tab. **Restore** undoes it.
- **Delete** (Owner only) asks you to type the project name. Members lose access immediately; data is purged after 30 days.

Each project's documents, modules and history are visible only to its members.

## Roles

| Role | Can |
| --- | --- |
| Owner | Everything, including deleting the project and granting Owner |
| Admin | Edit project details, archive/restore, manage members (below Owner), delete modules |
| QA Engineer | Upload and edit documents, create and edit modules, run AI extraction, add, edit, approve and reject requirements |
| Viewer | Read and download |

Add members in **Members** by email; the person must already have an account. Anyone can **Leave** a project, except its last Owner.

## Modules

Modules are the product's main areas (for example Authentication, Booking, Payments). In **Modules**:

- **New module** to add one; names are unique within the project.
- **Connections** records which modules a module depends on or affects. Later phases use this for retrieval scope and change impact analysis.

## Documents

In **Documents → Upload documents**, drop or choose files, pick a type (requirement, design, business logic, API documentation, existing test cases, screenshot, other) and optionally a module.

- Supported: PDF, DOCX, XLSX, CSV, TXT, MD, JSON, PNG, JPG, WebP, up to 25 MB each.
- The same file cannot be uploaded twice in a project; you are told which document already holds it.
- Every upload is read and indexed in the background: **Queued → Indexed**. PDF pages, Word headings and tables, and spreadsheet sheets are kept, so search results and citations can name the page or sheet.
- Scanned pages and images need OCR on the server. Without it the document shows **No text found** with a warning; after OCR is installed, open the document and choose **Reprocess**.
- Open a document to edit its title, type and module, see its versions and how many searchable passages it has, upload a new version, download any version, read the extracted text, reprocess or delete it.

## Knowledge search

**Knowledge search** finds passages in this project's current documents by meaning and by keyword, for example "when can a coupon not be applied?". Results show the document, version and page or sheet. Choosing a module also searches its connected modules and documents that have no module. Other projects' documents are never searched.

## Requirements

**Requirements** (in the project, or via **Requirement Analysis** in the sidebar) is the reviewed list of what the product must do. Every requirement has a permanent key such as `REQ-001`.

- **Add requirement** to write one yourself.
- **Extract with AI** (when an administrator has configured a language model): pick indexed documents and, optionally, add instructions. The AI proposes requirements as **drafts**. Each one quotes the exact sentence it came from; proposals whose quotes cannot be found in the document are thrown away. The result panel lists how many were created, merged or flagged, and **open questions** the documents leave unanswered.
- Open a requirement to see its sources (quote, document, page), approve or reject it, or edit it. Editing never overwrites: it saves a new version, and an approved requirement goes back to **Draft** until someone approves the new version. **History** shows every version; **Compare** shows what changed.
- A warning such as "similar to REQ-004" marks a likely duplicate. Compare before approving.
- Filter by status, type, priority and module, search by key or text, and approve or reject several at once.

## Activity and dashboard

- **Activity** lists every change in the project with who made it and when.
- The **Dashboard** shows totals (including requirements and approved requirements), recent activity and background jobs across all your projects, computed from stored data only. Test case, gap, bug and automation metrics appear when those modules ship.
