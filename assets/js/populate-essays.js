let sortLikesAscending = false;
let sortDatesAscending = false;
let showHTML = true;

function sortEssaysByDate(data) {
    sortDatesAscending = !sortDatesAscending;  // Toggle the sort order
    return data.sort((a, b) => sortDatesAscending
        ? new Date(a.date) - new Date(b.date)
        : new Date(b.date) - new Date(a.date));
}

function sortEssaysByLikes(data) {
    sortLikesAscending = !sortLikesAscending;  // Toggle the sort order
    return data.sort((a, b) => sortLikesAscending
        ? a.like_count - b.like_count
        : b.like_count - a.like_count);
}
function populateEssays(data) {
    // Built via DOM APIs (not innerHTML/template strings) because essay.title
    // and essay.subtitle come from scraped, untrusted third-party post content.
    const essaysContainer = document.getElementById('essays-container');
    const listEl = document.createElement('ul');

    for (const essay of data) {
        const li = document.createElement('li');

        const link = document.createElement('a');
        link.href = '../' + (showHTML ? essay.html_link : essay.file_link);
        link.target = '_blank';
        link.textContent = essay.title;
        li.appendChild(link);

        const subtitle = document.createElement('div');
        subtitle.className = 'subtitle';
        subtitle.textContent = essay.subtitle;
        li.appendChild(subtitle);

        const metadata = document.createElement('div');
        metadata.className = 'metadata';
        metadata.textContent = `${essay.like_count} Likes - ${essay.date}`;
        li.appendChild(metadata);

        listEl.appendChild(li);
    }

    essaysContainer.innerHTML = '';
    essaysContainer.appendChild(listEl);
}


document.addEventListener('DOMContentLoaded', () => {
    const embeddedDataElement = document.getElementById('essaysData');
    let essaysData = JSON.parse(embeddedDataElement.textContent);

    // Check if the toggle button exists to maintain backwards compatibility
    const toggleButton = document.getElementById('toggle-format');
    if (toggleButton) {
        toggleButton.addEventListener('click', () => {
            showHTML = !showHTML;
            populateEssays(essaysData);
            toggleButton.textContent = showHTML ? 'Show Markdown' : 'Show HTML';
        });
    }
    else {
        showHTML = false;  // Default to showing markdown as there won't be any html files in older versions
    }

    document.getElementById('sort-by-date').addEventListener('click', () => {
        populateEssays(sortEssaysByDate([...essaysData]));
    });

    document.getElementById('sort-by-likes').addEventListener('click', () => {
        populateEssays(sortEssaysByLikes([...essaysData]));
    });

    populateEssays(essaysData);
});
