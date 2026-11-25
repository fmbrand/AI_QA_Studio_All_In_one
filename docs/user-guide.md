# User guide (Phase 1)

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
| QA Engineer | Upload and edit documents, create and edit modules and their connections |
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
- Status: **Queued** → **Text extracted** for text, Markdown, CSV and JSON. PDF, Word, Excel and images show **Stored**; their text extraction arrives with Phase 2.
- Open a document to edit its title, type and module, see its versions, **Upload new version**, download any version, read the extracted text, or delete it.

## Activity and dashboard

- **Activity** lists every change in the project with who made it and when.
- The **Dashboard** shows totals, recent activity and background jobs across all your projects, computed from stored data only. Test case, gap, bug and automation metrics appear when those modules ship.
