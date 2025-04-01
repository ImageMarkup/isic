import S3FileFieldClient from "django-s3-file-field";

function formatBytes(bytes: number, decimals = 2) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

function SupplementalFileUploader() {
  const csrfToken = JSON.parse(document.getElementById("csrf-token")?.textContent!);
  const s3ffClient = new S3FileFieldClient({
    baseUrl: "/api/v2/s3-upload/",
    apiConfig: {
      headers: {
        "X-CSRFToken": csrfToken,
      },
    },
  });

  return {
    files: [],
    descriptions: [],
    _fieldValues: [],
    numFilesInProgress: 0,

    removeFile(index: number) {
      this.files.splice(index, 1);
      this.descriptions.splice(index, 1);
      this._fieldValues.splice(index, 1);
    },

    async handleFileUpload(event: Event) {
      if (this.files.length >= 10) {
        alert("You can only upload up to 10 supplemental files.");
        return;
      }

      const file = (event.target as HTMLInputElement).files![0];
      this.files.push(file);
      this.descriptions.push("");

      this.numFilesInProgress++;
      const fieldValue = await s3ffClient.uploadFile(file, "core.SupplementalFile.blob");
      this._fieldValues.push(fieldValue);
      this.numFilesInProgress--;
    },

    async createDOI(collectionId: number) {
      const response = await fetch("/api/v2/doi/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          collection_id: collectionId,
          supplemental_files: this._fieldValues.map((fieldValue, index) => ({
            blob: fieldValue.value,
            description: this.descriptions[index],
          })),
        }),
      });

      if (response.ok) {
        window.location.href = `/collections/${collectionId}`;
      } else {
        alert("Failed to create DOI");
      }
    },
  };
}

globalThis.SupplementalFileUploader = SupplementalFileUploader;
globalThis.formatBytes = formatBytes;
