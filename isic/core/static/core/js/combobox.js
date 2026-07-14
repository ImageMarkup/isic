function filterOptions(event, widgetName) {
  const selectInput = $(`#${widgetName}-select`);
  selectInput.find("option").each((i, item) => {
    if (item.title.toLocaleLowerCase().includes(
      event.target.value.toLocaleLowerCase()
    )) {
      item.classList.remove("hidden");
    } else {
      item.classList.add("hidden");
    }
  });
  optionMatchesUpdated(widgetName);
}

function optionMatchesUpdated(widgetName) {
  const selectInput = $(`#${widgetName}-select`);
  const matchesFound = selectInput.find("option").not(".hidden").length > 0;
  selectInput.find("#no-matches-found").each((i, item) => {
    if (matchesFound) {
      item.classList.add("hidden");
    } else {
      item.classList.remove("hidden");
    }
  });
}

function selectionUpdated(widgetName) {
  const selectedContainer = $(`#${widgetName}-selected`);
  const searchInput = $(`#${widgetName}-input`);
  const selectInput = $(`#${widgetName}-select`);
  selectedContainer.empty();
  selectInput.find("option:selected").each((i, item) => {
    const chip = $("<div>", {
      text: item.title,
      "class": "selection-chip px-2 py-0.5 text-xs font-semibold rounded-full bg-gray-100",
      css: {
        "pointer-events": "all",
        "white-space": "nowrap",
      },
      mousedown: (event) => {
        event.preventDefault();
        selectInput.val(selectInput.val().filter((v) => v !== item.value));
        selectionUpdated(widgetName);
      }
    });
    selectedContainer.append(chip);
  });
  const cursor = { top: undefined, left: undefined, bottom: undefined };
  const lastChip = selectedContainer.children().last();
  if (lastChip.length) {
    cursor.top = lastChip.position().top;
    cursor.left = lastChip.position().left + lastChip.width() + 40;
    if (cursor.left > searchInput.outerWidth() - 40) {
      cursor.left = 0;
      cursor.top += 24;
    }
    cursor.bottom = cursor.top + lastChip.height() + 8;
  }
  searchInput.css({
    "padding-top": cursor.top ? cursor.top + "px" : "",
    "padding-left": cursor.left ? cursor.left + "px" : "",
    "height": cursor.bottom ? cursor.bottom + "px" : "",
  });
  selectInput.css({
    "top": cursor.bottom ? (cursor.bottom + 4) + "px" : "",
  });
}

function submitOptionModal(action, option) {
  let promise = undefined;
  if (action == "delete") {
    promise = axiosSession.delete(
      `/api/v2/collections/tags/${option.id}/`
    )
  } else {
    const newValue = $("#new-option-input").val();
    if (action == 'edit') {
      promise = axiosSession.patch(
        `/api/v2/collections/tags/${option.id}/`,
        { tag: newValue },
      )
    } else if (action == 'create') {
      promise = axiosSession.post(
        `/api/v2/collections/tags`,
        { tag: newValue },
      )
    }
  }
  if (promise) {
    promise.then((data) => {
      window.location.reload();
    }).catch((error) => {
      const errorMessage = $("<div>", {
        text: error.response.data.error,
        "class": "bg-red-100 px-4 py-2 rounded"
      });
      $("#optionModalErrors").append(errorMessage);
    });
  }
}
