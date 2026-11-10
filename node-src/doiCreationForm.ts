type RelationType = "IsReferencedBy" | "IsSupplementedBy" | "IsDescribedBy";
type RelatedIdentifierType = "DOI" | "URL";

type RelationTypeConfig = {
  type: RelationType,
  title: string,
  description: string,
  examples: string,
  buttonText: string,
  emptyMessage: string,
  helpUrl: string,
  doiExample: string,
  urlExample: string,
  unique?: boolean,
};

type RelationTypeIdentifier = {
  relation_type: RelationType,
  related_identifier_type: RelatedIdentifierType,
  related_identifier: string,
};

type PartialRelationTypeIdentifier = {
  relation_type: RelationTypeIdentifier["relation_type"],
  related_identifier_type: string,
  related_identifier: string,
};

type SupplementalFile = {
  // A stable key, as rows may be removed from the middle
  id: number,
  // The value of the row's <s3-file-input>, empty until its upload completes
  blob: string,
  description: string,
};

type RelationTypeIdentifierArray = (RelationTypeIdentifier | PartialRelationTypeIdentifier)[];


function DoiCreationForm() {
  let nextFileId = 0;

  const relatedIdentifierTypeExamples = {
    doiExample: "10.7910/DVN.DBW86T",
    urlExample: "https://github.com/username/repo",
  };

  const identifiers: Record<string, RelationTypeIdentifierArray> = {
    referencedByIdentifiers: [],
    supplementedByIdentifiers: [],
    describedByIdentifiers: [],
  };

  const relationTypes: RelationTypeConfig[] = [
    {
      type: "IsDescribedBy",
      title: "Data Descriptor Publication",
      description: "A single publication that authoritatively describes this dataset.",
      examples: "Nature Scientific Data article",
      buttonText: "Add Descriptor",
      emptyMessage: "No descriptor added yet",
      helpUrl: "https://datacite-metadata-schema.readthedocs.io/en/4.6/appendices/appendix-1/relationType/#isdescribedby",
      ...relatedIdentifierTypeExamples,
      unique: true,
    },
    {
      type: "IsSupplementedBy",
      title: "External Supplemental Materials",
      description: "External resources that provide supplemental material for this dataset.",
      examples: "Figshare, GitHub Repositories",
      buttonText: "Add Supplement",
      emptyMessage: "No supplements added yet",
      helpUrl: "https://datacite-metadata-schema.readthedocs.io/en/4.6/appendices/appendix-1/relationType/#issupplementedby",
      ...relatedIdentifierTypeExamples,
    },
    {
      type: "IsReferencedBy",
      title: "Inbound References",
      description: "Publications, articles, or other works that cite or reference this dataset.<br />A mirror of this dataset.",
      examples: "Nature article, Harvard Dataverse, Kaggle",
      buttonText: "Add Reference",
      emptyMessage: "No references added yet",
      helpUrl: "https://datacite-metadata-schema.readthedocs.io/en/4.6/appendices/appendix-1/relationType/#isreferencedby",
      ...relatedIdentifierTypeExamples,
    },

  ];


  return {
    description: "",
    files: [] as SupplementalFile[],
    maxFiles: 10,
    ...identifiers,
    relationTypes,

    init() {
      this.description = JSON.parse(document.getElementById("collection-description")!.textContent!);
    },

    addFile() {
      if (this.files.length < this.maxFiles) {
        this.files.push({ id: nextFileId++, blob: "", description: "" });
      }
    },

    removeFile(index: number) {
      this.files.splice(index, 1);
    },

    addRelatedIdentifier(relationType: RelationType) {
      const relationConfig: RelationTypeConfig | undefined = this.relationTypes.find(r => r.type === relationType);
      const identifierArray: RelationTypeIdentifierArray = this.getIdentifiersArray(relationType);

      // account for IsDescribedBy being unique
      if (relationConfig?.unique && identifierArray.length > 0) {
        return;
      }

      const partialIdentifier: PartialRelationTypeIdentifier = {
        relation_type: relationType,
        related_identifier_type: "",
        related_identifier: "",
      };

      identifierArray.push(partialIdentifier);
    },

    getIdentifiersArray(relationType: RelationType): RelationTypeIdentifierArray {
      const propertyMap: Record<RelationType, keyof typeof identifiers> = {
        IsReferencedBy: 'referencedByIdentifiers',
        IsSupplementedBy: 'supplementedByIdentifiers',
        IsDescribedBy: 'describedByIdentifiers',
      };
      const propertyName = propertyMap[relationType];
      return this[propertyName] || [];
    },

    removeRelatedIdentifier(relationType: RelationType, index: number) {
      const identifierArray = this.getIdentifiersArray(relationType);
      identifierArray.splice(index, 1);
    },

    getPlaceholder(identifierType: RelatedIdentifierType, relationConfig: RelationTypeConfig) {
      if (identifierType === "DOI") {
        return `e.g., ${relationConfig.doiExample}`;
      } else if (identifierType === "URL") {
        return `e.g., ${relationConfig.urlExample}`;
      }

      return "Select type first";
    },

    async createDOI(collectionId: number) {
      const csrfToken = document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")!.value;
      const response = await fetch("/api/v2/doi/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          collection_id: collectionId,
          description: this.description,
          supplemental_files: this.files.map(({ blob, description }) => ({ blob, description })),
          // flatmap
          related_identifiers: this.relationTypes.flatMap(rt => this.getIdentifiersArray(rt.type)),
        }),
      });

      if (response.ok) {
        const data = await response.json();
        window.location.href = `/doi/${data.slug}`;
      } else {
        let errorMessage = "Failed to create DOI";
        const errorData = await response.json();

        if (errorData.message) {
          errorMessage = errorData.message;
        } else if (errorData.detail) {
          // this only grabs the first error, but is probably okay given server side errors for DOI creation
          // are extremely unlikely.
          errorMessage = errorData.detail[0].msg;
        }

        alert(errorMessage);
      }
    },
  };
}

globalThis.DoiCreationForm = DoiCreationForm;
