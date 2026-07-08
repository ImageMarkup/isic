function filterOptions(event, widgetName) {
  $(`#${widgetName}-select`).find("option").each((i, item) => {
    if (item.title.toLocaleLowerCase().includes(
      event.target.value.toLocaleLowerCase()
    )) {
      item.classList.remove('hidden');
    } else {
      item.classList.add('hidden');
    }
  })
}

function selectionUpdated(widgetName) {
  const selectedContainer = $(`#${widgetName}-selected`);
  const searchInput = $(`#${widgetName}-input`);
  const selectInput = $(`#${widgetName}-select`);
  selectedContainer.empty();
  selectInput.find("option:selected").each((i, item) => {
    const chip = $("<div>", {
      text: item.title,
      'class': 'selection-chip px-2 py-0.5 text-xs font-semibold rounded-full bg-gray-100',
      css: {
        'pointer-events': 'all',
        'white-space': 'nowrap',
      },
      mousedown: (event) => {
        event.preventDefault();
        selectInput.val(selectInput.val().filter((v) => v !== item.value));
        selectionUpdated(widgetName);
      }
    });
    selectedContainer.append(chip);
  });
  const cursor = {top: undefined, left: undefined, bottom: undefined};
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
