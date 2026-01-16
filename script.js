// Variáveis globais
let allGalleryImagesData = [];
let allTimelineEventsData = {};
let currentModalImageList = [];
let currentModalImageIndex = -1;
let activeGalleryTags = new Set();

// --- ELEMENTOS DO DOM (serão definidos dentro de DOMContentLoaded) ---
let imageDisplayModal, modalDisplayedImage, imageDisplayModalTitle, modalImageCaption,
    modalImageCorroborationText, closeImageDisplayModalButton, imageZoomContainer,
    zoomInButton, zoomOutButton, resetZoomButton, openImageNewTabButton,
    prevImageButton, nextImageButton, loadingIndicator, galleryTagsContainer,
    galleryTagFiltersContainer, clearGalleryTagsFilterButton, toggleTagFiltersVisibilityButton, 
    galleryTagsWrapper, tagFilterChevron, searchControlsWrapper;


// --- LÓGICA DO MODAL DE IMAGEM (ZOOM, PAN, NAVEGAÇÃO) ---
let currentZoomLevel = 1;
const zoomStep = 0.15;
const maxZoom = 3;
const minZoom = 0.3;
let isPanning = false;
let panStartX, panStartY;
let currentPanX = 0;
let currentPanY = 0;
// Variáveis para suavizar o pan
let panTargetX = 0;
let panTargetY = 0;

function applyTransform() { 
    if (modalDisplayedImage) {
        modalDisplayedImage.style.transform = `translate(${currentPanX}px, ${currentPanY}px) scale(${currentZoomLevel})`;
        modalDisplayedImage.style.cursor = currentZoomLevel > 1 ? 'grab' : 'zoom-in';
        if (isPanning) modalDisplayedImage.style.cursor = 'grabbing';
    }
}

// Loop de animação para suavizar o movimento de arrastar (pan)
function panAnimationLoop() {
    if (!isPanning) return; // Encerra o loop se não estiver mais arrastando

    // Interpola suavemente a posição atual para a posição alvo
    currentPanX += (panTargetX - currentPanX) * 0.2;
    currentPanY += (panTargetY - currentPanY) * 0.2;
    applyTransform();
    
    // Continua o loop de animação
    requestAnimationFrame(panAnimationLoop);
}

function startPan(e) {
    if (currentZoomLevel > 1) {
        e.preventDefault();
        isPanning = true;
        const event = e.touches ? e.touches[0] : e;
        panStartX = event.clientX - panTargetX; // Usa o alvo para evitar saltos
        panStartY = event.clientY - panTargetY;
        modalDisplayedImage.style.cursor = 'grabbing';
        requestAnimationFrame(panAnimationLoop); // Inicia o loop de animação
    }
}

function doPan(e) {
    if (isPanning) {
        e.preventDefault();
        const event = e.touches ? e.touches[0] : e;
        // Apenas atualiza a posição alvo, a animação fará o resto
        panTargetX = event.clientX - panStartX;
        panTargetY = event.clientY - panStartY;
    }
}

function endPan() {
    if(isPanning) {
        isPanning = false;
        if (modalDisplayedImage) {
            modalDisplayedImage.style.cursor = currentZoomLevel > 1 ? 'grab' : 'zoom-in';
        }
        // A posição final será alcançada suavemente pelo panAnimationLoop
    }
}


function zoomImage(direction) {
    const oldZoom = currentZoomLevel;
    if (direction === 'in' && currentZoomLevel < maxZoom) {
        currentZoomLevel = Math.min(currentZoomLevel + zoomStep, maxZoom);
    } else if (direction === 'out' && currentZoomLevel > minZoom) {
        currentZoomLevel = Math.max(currentZoomLevel - zoomStep, minZoom);
    }
    currentZoomLevel = Math.round(currentZoomLevel * 100) / 100;
    if (currentZoomLevel <= 1 && oldZoom > 1) {
        currentPanX = 0; currentPanY = 0;
        panTargetX = 0; panTargetY = 0;
    }
    applyTransform();
}

function resetZoomAndPan() { 
    currentZoomLevel = 1; currentPanX = 0; currentPanY = 0;
    panTargetX = 0; panTargetY = 0;
    applyTransform();
}

function updateModalNavigationButtons() {
    if (!prevImageButton || !nextImageButton) return;
    const canGoPrev = currentModalImageIndex > 0;
    const canGoNext = currentModalImageIndex < currentModalImageList.length - 1;
    prevImageButton.disabled = !canGoPrev;
    nextImageButton.disabled = !canGoNext;
}

function showImageInModalByIndex(newIndex) {
    if (newIndex >= 0 && newIndex < currentModalImageList.length) {
        currentModalImageIndex = newIndex;
        const imageData = currentModalImageList[currentModalImageIndex];
        const imagePath = `/static/pesquisa_imagens/${imageData.fileName.trim()}`;
        const corroborationHtml = imageData.corroboration ? `<strong>Corroboração:</strong><br>${imageData.corroboration.replace(/\n/g, '<br>')}` : '';
        
        if (!imageDisplayModal || !modalDisplayedImage || !imageDisplayModalTitle || !modalImageCaption || !modalImageCorroborationText) return;
        
        modalDisplayedImage.style.transition = 'opacity 0.15s ease-out';
        modalDisplayedImage.style.opacity = '0';
        setTimeout(() => {
            modalDisplayedImage.src = imagePath;
            modalDisplayedImage.alt = `Imagem ampliada de ${imageData.fileName || 'imagem'}`;
            imageDisplayModalTitle.textContent = `Visualizar: ${imageData.fileName || imageData.title || 'Imagem'}`;
            modalImageCaption.textContent = imageData.title || (imageData.fileName ? `Fonte: ${imageData.fileName}` : 'Imagem da Galeria');
            modalImageCorroborationText.innerHTML = corroborationHtml || '';
            resetZoomAndPan();
            modalDisplayedImage.style.opacity = '1';
        }, 150);
        updateModalNavigationButtons();
    }
}

function openImageInModalWithControls(imageSrc, imageName, contextTitle, corroborationHtml = '', imageList = [], currentIndex = -1) {
    if (!imageDisplayModal) return;
    imageDisplayModal.classList.remove('hidden');
    const modalContent = imageDisplayModal.querySelector('.modal-content');
    
    void imageDisplayModal.offsetWidth; 
    imageDisplayModal.classList.remove('opacity-0');
    if (modalContent) {
        modalContent.classList.remove('scale-95', 'opacity-0');
        void modalContent.offsetWidth;
        modalContent.classList.add('scale-100', 'opacity-100');
    }

    if (modalDisplayedImage) modalDisplayedImage.src = imageSrc;
    if (imageDisplayModalTitle) imageDisplayModalTitle.textContent = `Visualizar: ${imageName || contextTitle || 'Imagem'}`;
    if (modalImageCaption) modalImageCaption.textContent = contextTitle || (imageName ? `Fonte: ${imageName}` : 'Imagem da Galeria');
    if (modalImageCorroborationText) modalImageCorroborationText.innerHTML = corroborationHtml || '';
    
    currentModalImageList = imageList;
    currentModalImageIndex = currentIndex;
    
    resetZoomAndPan();
    document.body.classList.add('overflow-hidden');
    updateModalNavigationButtons();
}

function closeImageDisplayModal() {
    if (imageDisplayModal) {
        imageDisplayModal.classList.add('opacity-0');
        const modalContent = imageDisplayModal.querySelector('.modal-content');
        if (modalContent) {
            modalContent.classList.remove('scale-100', 'opacity-100');
            modalContent.classList.add('scale-95', 'opacity-0');
        }
        setTimeout(() => {
            imageDisplayModal.classList.add('hidden');
            document.body.classList.remove('overflow-hidden');
            resetZoomAndPan();
            currentModalImageList = [];
            currentModalImageIndex = -1;
        }, 300);
    }
}

// --- LÓGICA DA TIMELINE ---
function createTimelineItem(event, eventList) {
    const item = document.createElement('div');
    item.className = 'timeline-item ml-4 pl-8 pt-1 pb-4 relative timeline-event animate-slide-up-subtle';
    item.dataset.year = event.year || '';
    item.dataset.title = event.title || '';
    item.dataset.text = event.text || '';

    const dot = document.createElement('div');
    dot.className = 'timeline-dot w-4 h-4 rounded-full absolute -left-[9.5px] top-1 shadow-md';
    item.appendChild(dot);

    const titleElement = document.createElement('h4');
    titleElement.className = 'event-title text-lg font-semibold mb-1 cursor-pointer';
    let displayTitle = event.year ? `<span class="event-year text-sm font-medium text-gray-500 dark:text-gray-400 mr-2">(${event.year})</span>` : '';
    displayTitle += event.title || "Evento Sem Título";
    titleElement.innerHTML = displayTitle;
    titleElement.dataset.originalHtml = displayTitle;
    item.appendChild(titleElement);

    const detailsDiv = document.createElement('div');
    detailsDiv.className = 'event-details text-sm leading-relaxed';
    const textP = document.createElement('p');
    textP.className = 'py-2 event-text-content';
    textP.innerHTML = `<strong>📜 Informação:</strong> ${event.text || "Nenhuma descrição disponível."}`;
    textP.dataset.originalHtml = textP.innerHTML;
    detailsDiv.appendChild(textP);

    if (event.images && Array.isArray(event.images) && event.images.length > 0) {
        const imageThumbContainer = document.createElement('div');
        imageThumbContainer.className = 'mt-3 flex flex-wrap gap-2';
        const timelineImagesForModal = event.images.map(imgName => ({
            fileName: imgName, title: event.title, corroboration: event.corroboracao
        }));
        event.images.forEach((imageName, index) => {
            if (imageName && typeof imageName === 'string' && imageName.trim() !== '') {
                const imgThumbnail = document.createElement('img');
                const imagePath = `/static/pesquisa_imagens/${imageName.trim()}`;
                imgThumbnail.src = imagePath;
                imgThumbnail.loading = 'lazy';
                imgThumbnail.alt = `Miniatura de ${imageName.trim()}`;
                imgThumbnail.className = 'timeline-image-thumbnail h-16 w-16 object-cover rounded-md cursor-pointer border border-gray-200 dark:border-gray-700 hover:opacity-80 transition-opacity duration-150';
                imgThumbnail.addEventListener('error', function() { this.style.display = 'none'; console.warn(`Timeline img not found: ${imagePath}`); });
                imgThumbnail.addEventListener('click', (e) => {
                    e.stopPropagation();
                    openImageInModalWithControls(
                        imagePath, imageName.trim(), event.title || "Imagem da Timeline",
                        event.corroboracao ? `<strong>Corroboração do Evento:</strong><br>${event.corroboracao.replace(/\n/g, '<br>')}` : '',
                        timelineImagesForModal, index
                    );
                });
                imageThumbContainer.appendChild(imgThumbnail);
            }
        });
        if (imageThumbContainer.children.length > 0) detailsDiv.appendChild(imageThumbContainer);
    }
    if (event.corroboracao) {
        const sourceDiv = document.createElement('div');
        sourceDiv.className = 'source-ref p-3 mt-4 rounded-md text-xs';
        const corroboracaoP = document.createElement('p');
        corroboracaoP.innerHTML = `<strong>🔎 Corroboração do Evento:</strong> ${event.corroboracao.replace(/\n/g, '<br>')}`;
        sourceDiv.appendChild(corroboracaoP);
        detailsDiv.appendChild(sourceDiv);
    }
    item.appendChild(detailsDiv);
    titleElement.addEventListener('click', () => {
        const isOpen = detailsDiv.classList.toggle('open');
        detailsDiv.style.maxHeight = isOpen ? detailsDiv.scrollHeight + "px" : '0px';
    });
    return item;
}

async function fetchAndPopulateTimelineSection(sectionName, containerSelector) {
    const mainContainer = document.querySelector(containerSelector);
    if (!mainContainer) { console.error(`Timeline container ${containerSelector} not found.`); return; }
    if (loadingIndicator) {
        loadingIndicator.style.display = 'flex';
        void loadingIndicator.offsetWidth;
        loadingIndicator.classList.remove('opacity-0');
    }
    mainContainer.innerHTML = '';

    try {
        const response = await fetch(`/api/timeline/${sectionName.toLowerCase()}`);
        if (!response.ok) throw new Error(`Erro HTTP ${response.status}`);
        const events = await response.json();
        allTimelineEventsData[sectionName.toLowerCase()] = events;
        mainContainer.innerHTML = '';
        if (!events || events.length === 0) {
            mainContainer.innerHTML = `<p class="text-center text-gray-500 dark:text-gray-400 py-4">Nenhum evento encontrado para ${sectionName}.</p>`;
        } else {
            events.forEach((event, index) => {
                 const eventElement = createTimelineItem(event, events);
                 eventElement.style.animationDelay = `${index * 0.05}s`;
                 mainContainer.appendChild(eventElement);
            });
        }
    } catch (error) {
        console.error(`Erro timeline ${sectionName}:`, error);
        mainContainer.innerHTML = `<p class="text-red-500 p-4 text-center">Erro ao carregar timeline. Detalhe: ${error.message}</p>`;
    } finally {
        setTimeout(() => {
            if (loadingIndicator) {
                loadingIndicator.classList.add('opacity-0');
                setTimeout(() => {
                    loadingIndicator.style.display = 'none';
                }, 300);
            }
        }, 250);
    }
}

// --- LÓGICA DA GALERIA CONTEXTUAL, CRONOLÓGICA E COM FILTRO DE TAGS ---
function populateTagFilters() {
    if (!galleryTagsContainer || !allGalleryImagesData || !galleryTagFiltersContainer) return;
    const uniqueTags = new Set();
    allGalleryImagesData.forEach(image => (image.tags || []).forEach(tag => uniqueTags.add(tag.trim())));

    galleryTagsContainer.innerHTML = '';
    if (uniqueTags.size === 0) {
        galleryTagFiltersContainer.style.display = 'none';
        if (galleryTagsWrapper) galleryTagsWrapper.style.maxHeight = '0px';
        if (toggleTagFiltersVisibilityButton) toggleTagFiltersVisibilityButton.setAttribute('aria-expanded', 'false');
        if (tagFilterChevron) {
            tagFilterChevron.classList.remove('fa-chevron-up');
            tagFilterChevron.classList.add('fa-chevron-down');
        }
        
        return;
    }
    galleryTagFiltersContainer.style.display = 'block';

    Array.from(uniqueTags).sort().forEach(tag => {
        const button = document.createElement('button');
        button.className = 'tag-filter-button';
        button.textContent = tag;
        button.dataset.tag = tag;
        button.classList.toggle('active', activeGalleryTags.has(tag));
        button.setAttribute('aria-pressed', activeGalleryTags.has(tag).toString());
        button.addEventListener('click', () => {
            activeGalleryTags.has(tag) ? activeGalleryTags.delete(tag) : activeGalleryTags.add(tag);
            button.classList.toggle('active');
            button.setAttribute('aria-pressed', activeGalleryTags.has(tag).toString());
            if (clearGalleryTagsFilterButton) clearGalleryTagsFilterButton.style.display = activeGalleryTags.size > 0 ? 'inline-block' : 'none';
            renderGalleryWithContextualTopics(allGalleryImagesData);
        });
        galleryTagsContainer.appendChild(button);
    });
    if (clearGalleryTagsFilterButton) clearGalleryTagsFilterButton.style.display = activeGalleryTags.size > 0 ? 'inline-block' : 'none';
}


function createGalleryTopicItem(imageData, imageListInTopic, currentIndexInTopic) {
    const item = document.createElement('div');
    item.className = 'gallery-item p-2 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm hover:shadow-lg transform hover:scale-105 transition-all duration-200 flex flex-col items-center text-center cursor-pointer h-48 animate-fade-in-subtle';
    const imgThumbnail = document.createElement('img');
    const imagePath = `/static/pesquisa_imagens/${imageData.fileName.trim()}`;
    imgThumbnail.src = imagePath;
    imgThumbnail.alt = imageData.title || imageData.fileName;
    imgThumbnail.className = 'gallery-thumbnail w-full h-32 object-contain mb-2 rounded';
    imgThumbnail.loading = 'lazy';
    imgThumbnail.addEventListener('error', function() { this.style.display = 'none'; console.warn(`Imagem da galeria não encontrada: ${imagePath}`);});
    const imageNameSpan = document.createElement('span');
    imageNameSpan.className = 'gallery-item-name text-xs font-medium text-gray-700 dark:text-gray-300 mt-auto overflow-hidden text-ellipsis whitespace-nowrap w-full';
    imageNameSpan.textContent = imageData.title || imageData.fileName.split('.')[0].replace(/_/g, ' ');
    item.appendChild(imgThumbnail);
    item.appendChild(imageNameSpan);
    item.addEventListener('click', () => {
        const corroborationForModal = imageData.corroboration ? `<strong>Corroboração:</strong><br>${imageData.corroboration.replace(/\n/g, '<br>')}` : '';
        openImageInModalWithControls(imagePath, imageData.fileName.trim(), imageData.title || `Fonte: ${imageData.fileName.trim()}`, corroborationForModal, imageListInTopic, currentIndexInTopic);
    });
    return item;
}

function renderGalleryWithContextualTopics(allImagesMasterList) {
    const galleryGridContainer = document.getElementById('imageGalleryGrid');
    const noResultsMessageGallery = document.getElementById('noResultsMessageGallery');
    if (!galleryGridContainer || !noResultsMessageGallery) {
        console.error("Elementos da galeria (imageGalleryGrid ou noResultsMessageGallery) não encontrados em renderGallery.");
        return;
    }
    galleryGridContainer.innerHTML = '';
    noResultsMessageGallery.style.display = 'none';

    const searchInputValue = document.getElementById('searchBar').value.toLowerCase();
    let imagesToFilter = [...allImagesMasterList];

    if (activeGalleryTags.size > 0) {
        imagesToFilter = imagesToFilter.filter(image => {
            const imageTags = new Set((image.tags || []).map(tag => tag.trim()));
            return Array.from(activeGalleryTags).every(activeTag => imageTags.has(activeTag));
        });
    }
    if (searchInputValue) {
        imagesToFilter = imagesToFilter.filter(img => {
            const title = img.title?.toLowerCase() || '';
            const fileName = img.fileName?.toLowerCase() || '';
            const corroboration = img.corroboration?.toLowerCase() || '';
            const adminSection = img.admin_assigned_section?.toLowerCase() || '';
            const detectedTopicsStr = (img.detected_topics || []).join(' ').toLowerCase();
            const imageTagsStr = (img.tags || []).join(' ').toLowerCase();
            return title.includes(searchInputValue) || fileName.includes(searchInputValue) || corroboration.includes(searchInputValue) || adminSection.includes(searchInputValue) || detectedTopicsStr.includes(searchInputValue) || imageTagsStr.includes(searchInputValue);
        });
    }
    const imagesToDisplay = imagesToFilter;

    if (imagesToDisplay.length === 0) {
        if (searchInputValue || activeGalleryTags.size > 0) {
            noResultsMessageGallery.textContent = "Nenhuma imagem encontrada para os filtros aplicados.";
            noResultsMessageGallery.style.display = 'block';
        } else {
            galleryGridContainer.innerHTML = "<p class='col-span-full text-center text-gray-500 dark:text-gray-400 py-4'>Nenhuma imagem na galeria ainda.</p>";
        }
        return;
    }

    const topics = { "Panceri": [], "Pompeia": [], "Scavino & Bertuzzi": [], "GERAL": [] };
    topics["GERAL"] = [...imagesToDisplay].sort((a,b) => (a.chronological_order || 0) - (b.chronological_order || 0));
    imagesToDisplay.forEach(image => {
        (image.detected_topics || []).forEach(topicName => {
            if (topics.hasOwnProperty(topicName) && topicName !== "GERAL") {
                 if (!topics[topicName].find(img => img.id === image.id)) topics[topicName].push(image);
            }
        });
    });
    for (const topicName in topics) {
        if (topicName !== "GERAL") topics[topicName].sort((a, b) => (a.chronological_order || 0) - (b.chronological_order || 0));
    }

    const topicOrder = ["Panceri", "Pompeia", "Scavino & Bertuzzi", "GERAL"];
    let topicAnimationDelayBase = 0;
    topicOrder.forEach(topicName => {
        const imagesInTopic = topics[topicName];
        if (imagesInTopic.length === 0) return;

        const topicContainer = document.createElement('div');
        topicContainer.className = 'gallery-topic-container mb-6 bg-white dark:bg-slate-800 shadow-md rounded-lg animate-fade-in-subtle';
        topicContainer.style.animationDelay = `${topicAnimationDelayBase}s`;
        topicAnimationDelayBase += 0.07;

        const topicHeader = document.createElement('button');
        topicHeader.className = 'gallery-subsection-title text-xl font-semibold content-subheading p-3 bg-gray-100 dark:bg-gray-700 rounded-t-lg shadow w-full flex justify-between items-center cursor-pointer focus:outline-none transition-colors duration-200 ease-in-out';
        const shouldStartExpanded = (searchInputValue && imagesInTopic.length > 0) || (activeGalleryTags.size > 0 && imagesInTopic.length > 0) || (topicName === "GERAL" && !searchInputValue && activeGalleryTags.size === 0 && imagesInTopic.length > 0);
        topicHeader.setAttribute('aria-expanded', shouldStartExpanded.toString());
        topicHeader.innerHTML = `<span>${topicName} (${imagesInTopic.length})</span><i class="fas ${shouldStartExpanded ? 'fa-chevron-down' : 'fa-chevron-right'} gallery-toggle-icon transition-transform duration-300"></i>`;
        if(shouldStartExpanded) topicHeader.classList.add('expanded');

        const imagesContainerWrapper = document.createElement('div');
        imagesContainerWrapper.className = 'gallery-images-wrapper overflow-hidden transition-all duration-500 ease-in-out';
        imagesContainerWrapper.style.maxHeight = shouldStartExpanded ? '5000px' : '0px';
        const imagesGridDiv = document.createElement('div');
        imagesGridDiv.className = 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 p-4';
        let itemAnimationDelay = 0;
        imagesInTopic.forEach((imgData, index) => {
            const galleryItem = createGalleryTopicItem(imgData, imagesInTopic, index);
            galleryItem.style.animationDelay = `${itemAnimationDelay}s`;
            itemAnimationDelay += 0.03;
            imagesGridDiv.appendChild(galleryItem);
        });
        if (imagesGridDiv.children.length === 0 && (searchInputValue || activeGalleryTags.size > 0)) {
            imagesGridDiv.innerHTML = `<p class="col-span-full text-sm text-center text-gray-500 dark:text-gray-400 py-2">Nenhuma imagem neste tópico para os filtros aplicados.</p>`;
        }
        imagesContainerWrapper.appendChild(imagesGridDiv);
        topicContainer.appendChild(topicHeader);
        topicContainer.appendChild(imagesContainerWrapper);
        galleryGridContainer.appendChild(topicContainer);
        if (shouldStartExpanded && imagesGridDiv.scrollHeight > 0) {
             setTimeout(() => { if(imagesGridDiv.scrollHeight > 0) imagesContainerWrapper.style.maxHeight = imagesGridDiv.scrollHeight + "px"; }, 50);
        }

        topicHeader.addEventListener('click', () => {
            const isCurrentlyHidden = imagesContainerWrapper.style.maxHeight === '0px' || imagesContainerWrapper.style.maxHeight === '';
            const icon = topicHeader.querySelector('.gallery-toggle-icon');
            topicHeader.classList.toggle('expanded', isCurrentlyHidden);
            if (isCurrentlyHidden) {
                imagesContainerWrapper.style.maxHeight = imagesGridDiv.scrollHeight + "px";
                if (icon) icon.classList.replace('fa-chevron-right', 'fa-chevron-down');
                topicHeader.setAttribute('aria-expanded', 'true');
            } else {
                imagesContainerWrapper.style.maxHeight = '0px';
                if (icon) icon.classList.replace('fa-chevron-down', 'fa-chevron-right');
                topicHeader.setAttribute('aria-expanded', 'false');
            }
        });
    });
}

async function fetchAndPopulateGallery() {
    if (!imageGalleryGrid) { console.error("Gallery grid not found for initial population."); return; } 
    if (loadingIndicator) {
        loadingIndicator.style.display = 'flex';
        void loadingIndicator.offsetWidth;
        loadingIndicator.classList.remove('opacity-0', 'pointer-events-none');
    }
    imageGalleryGrid.innerHTML = '';

    try {
        const response = await fetch('/api/gallery');
        if (!response.ok) throw new Error(`Erro HTTP ${response.status}`);
        allGalleryImagesData = await response.json();
        if (!Array.isArray(allGalleryImagesData)) allGalleryImagesData = [];
        allGalleryImagesData.sort((a, b) => (a.chronological_order || 0) - (b.chronological_order || 0));
        populateTagFilters();
        renderGalleryWithContextualTopics(allGalleryImagesData);
        if (document.getElementById('searchBar').value) performSearch(document.getElementById('searchBar').value);
    } catch (error) {
        console.error("Erro galeria:", error);
        if (imageGalleryGrid) imageGalleryGrid.innerHTML = `<p class="text-red-500 p-4 text-center">Erro ao carregar galeria: ${error.message}</p>`;
    } finally {
        setTimeout(() => {
            if (loadingIndicator) {
                loadingIndicator.classList.add('opacity-0');
                setTimeout(() => {
                    loadingIndicator.style.display = 'none';
                    loadingIndicator.classList.add('pointer-events-none');
                }, 300);
            }
        }, 300);
    }
}

// --- INICIALIZAÇÃO E EVENT LISTENERS GLOBAIS ---
document.addEventListener('DOMContentLoaded', async function() {
    // Atribuição de elementos do DOM às variáveis globais
    imageDisplayModal = document.getElementById('imageDisplayModal');
    modalDisplayedImage = document.getElementById('modalDisplayedImage');
    imageDisplayModalTitle = document.getElementById('imageDisplayModalTitle');
    modalImageCaption = document.getElementById('modalImageCaption');
    modalImageCorroborationText = document.getElementById('modalImageCorroborationText');
    closeImageDisplayModalButton = document.getElementById('closeImageDisplayModalButton');
    imageZoomContainer = document.getElementById('imageZoomContainer');
    zoomInButton = document.getElementById('zoomInButton');
    zoomOutButton = document.getElementById('zoomOutButton');
    resetZoomButton = document.getElementById('resetZoomButton');
    openImageNewTabButton = document.getElementById('openImageNewTabButton');
    prevImageButton = document.getElementById('prevImageButton');
    nextImageButton = document.getElementById('nextImageButton');
    loadingIndicator = document.getElementById('loading-indicator');
    galleryTagsContainer = document.getElementById('gallery-tags');
    galleryTagFiltersContainer = document.getElementById('gallery-tag-filters-container');
    clearGalleryTagsFilterButton = document.getElementById('clear-gallery-tags-filter');
    toggleTagFiltersVisibilityButton = document.getElementById('toggle-tag-filters-visibility');
    galleryTagsWrapper = document.getElementById('gallery-tags-wrapper');
    searchControlsWrapper = document.getElementById('search-controls-wrapper');
    tagFilterChevron = document.getElementById('tag-filter-chevron');
    
    const navButtons = document.querySelectorAll('.nav-button');
    const contentSections = document.querySelectorAll('.content-section');
    const searchBar = document.getElementById('searchBar');
    const clearSearchButton = document.getElementById('clearSearchButton');
    const executeSearchButton = document.getElementById('executeSearchButton');
    const darkModeToggle = document.getElementById('darkModeToggle');
    const htmlElement = document.documentElement;
    const darkModeIcon = darkModeToggle ? darkModeToggle.querySelector('.dark-mode-icon') : null;
    const lightModeIcon = darkModeToggle ? darkModeToggle.querySelector('.light-mode-icon') : null;
    const stickyHeaderNavWrapper = document.getElementById('stickyHeaderNavWrapper');
    let lastScrollY = window.scrollY;

    // Event Listeners do Modal (com zoom/pan restaurado)
    if (closeImageDisplayModalButton) closeImageDisplayModalButton.addEventListener('click', closeImageDisplayModal);
    if (imageDisplayModal) imageDisplayModal.addEventListener('click', (event) => { if (event.target === imageDisplayModal) closeImageDisplayModal(); });
    if (zoomInButton) zoomInButton.addEventListener('click', () => zoomImage('in'));
    if (zoomOutButton) zoomOutButton.addEventListener('click', () => zoomImage('out'));
    if (resetZoomButton) resetZoomButton.addEventListener('click', resetZoomAndPan);
    if (openImageNewTabButton && modalDisplayedImage) openImageNewTabButton.addEventListener('click', () => { if (modalDisplayedImage.src) window.open(modalDisplayedImage.src, '_blank'); });
    if (prevImageButton) prevImageButton.addEventListener('click', () => showImageInModalByIndex(currentModalImageIndex - 1));
    if (nextImageButton) nextImageButton.addEventListener('click', () => showImageInModalByIndex(currentModalImageIndex + 1));
    
    if (imageZoomContainer && modalDisplayedImage) {
        imageZoomContainer.addEventListener('wheel', (e) => { if (imageDisplayModal && !imageDisplayModal.classList.contains('hidden')) { e.preventDefault(); zoomImage(e.deltaY < 0 ? 'in' : 'out');}}, { passive: false });
        modalDisplayedImage.addEventListener('mousedown', startPan);
        modalDisplayedImage.addEventListener('touchstart', startPan, { passive: false });
    }
    window.addEventListener('mousemove', doPan);
    window.addEventListener('touchmove', doPan, { passive: false });
    window.addEventListener('mouseup', endPan);
    window.addEventListener('mouseleave', endPan);
    window.addEventListener('touchend', endPan);

    // Event Listeners dos Filtros
    if(clearGalleryTagsFilterButton){
        clearGalleryTagsFilterButton.addEventListener('click', () => {
            activeGalleryTags.clear();
            document.querySelectorAll('#gallery-tags .tag-filter-button.active').forEach(btn => {
                btn.classList.remove('active');
                btn.setAttribute('aria-pressed', 'false');
            });
            clearGalleryTagsFilterButton.style.display = 'none';
            renderGalleryWithContextualTopics(allGalleryImagesData);
        });
    }
    if(toggleTagFiltersVisibilityButton && galleryTagsWrapper && tagFilterChevron){
        toggleTagFiltersVisibilityButton.addEventListener('click', () => {
            const isHidden = galleryTagsWrapper.style.maxHeight === '0px' || galleryTagsWrapper.style.maxHeight === '';
            
            if(isHidden){
                galleryTagsWrapper.style.maxHeight = galleryTagsWrapper.scrollHeight + "px";
                tagFilterChevron.classList.replace('fa-chevron-down', 'fa-chevron-up');
                toggleTagFiltersVisibilityButton.setAttribute('aria-expanded', 'true');
            } else {
                galleryTagsWrapper.style.maxHeight = '0px';
                tagFilterChevron.classList.replace('fa-chevron-up', 'fa-chevron-down');
                toggleTagFiltersVisibilityButton.setAttribute('aria-expanded', 'false');
            }
        });
    }


    const currentYearEl = document.getElementById('currentYear');
    if (currentYearEl) currentYearEl.textContent = new Date().getFullYear();

    function setDarkMode(isDark) {
        htmlElement.classList.toggle('dark', isDark);
        if (darkModeIcon) darkModeIcon.style.display = isDark ? 'none' : 'inline';
        if (lightModeIcon) lightModeIcon.style.display = isDark ? 'inline' : 'none';
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
    }
    if (darkModeToggle) darkModeToggle.addEventListener('click', () => setDarkMode(!htmlElement.classList.contains('dark')));
    const savedTheme = localStorage.getItem('theme');
    setDarkMode(savedTheme === 'dark' || (!savedTheme && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches));

    if (loadingIndicator) {
        loadingIndicator.style.display = 'flex';
        void loadingIndicator.offsetWidth; 
        loadingIndicator.classList.remove('opacity-0');
    }
    await Promise.all([
        fetchAndPopulateTimelineSection('panceri', '#panceri .space-y-8'),
        fetchAndPopulateTimelineSection('pompeia', '#pompeia .space-y-8'),
        fetchAndPopulateTimelineSection('scavino', '#scavino .space-y-8'),
        fetchAndPopulateGallery()
    ]).finally(() => {
        if (loadingIndicator) {
            loadingIndicator.classList.add('opacity-0');
            setTimeout(() => {
                loadingIndicator.style.display = 'none';
            }, 300);
        }
    });

    function showSection(sectionId) {
        contentSections.forEach(section => {
            section.classList.remove('active-section');
            section.classList.add('hidden');
        });
        const targetSection = document.getElementById(sectionId === "sobre" ? "sobre-section" : sectionId);
        if (targetSection) {
            targetSection.classList.remove('hidden');
            targetSection.classList.add('active-section', 'animate-fade-in-subtle');
        }
        navButtons.forEach(button => button.classList.toggle('active', button.dataset.section === sectionId));
        
        if(searchControlsWrapper) searchControlsWrapper.style.display = (sectionId === 'sobre') ? 'none' : 'flex';
        if(galleryTagFiltersContainer) galleryTagFiltersContainer.style.display = (sectionId === 'gallery' && allGalleryImagesData.length > 0 && (galleryTagsContainer && galleryTagsContainer.children.length > 0) ) ? 'block' : 'none'; 
        
        if (searchBar) searchBar.value = '';
        activeGalleryTags.clear();
        if (clearGalleryTagsFilterButton) clearGalleryTagsFilterButton.style.display = 'none';
        document.querySelectorAll('#gallery-tags .tag-filter-button.active').forEach(btn => {
            btn.classList.remove('active');
            btn.setAttribute('aria-pressed','false');
        });
        if (toggleTagFiltersVisibilityButton && galleryTagsWrapper) {
            galleryTagsWrapper.style.maxHeight = '0px';
            if(tagFilterChevron) { tagFilterChevron.classList.remove('fa-chevron-up'); tagFilterChevron.classList.add('fa-chevron-down'); }
            toggleTagFiltersVisibilityButton.setAttribute('aria-expanded', 'false');
        }
        performSearch('');
    }

    navButtons.forEach(button => button.addEventListener('click', function() { showSection(this.dataset.section); }));

    function performSearch(searchTerm) {
        const normalizedSearchTerm = searchTerm.toLowerCase().trim();
        const activeSection = document.querySelector('.content-section.active-section');
        const noResultsMessageTimeline = document.getElementById('noResultsMessage');
        const noResultsMessageGallery = document.getElementById('noResultsMessageGallery');

        if (noResultsMessageTimeline) noResultsMessageTimeline.style.display = 'none';
        if (noResultsMessageGallery) noResultsMessageGallery.style.display = 'none';
        if (!activeSection) return;

        if (activeSection.id === 'panceri' || activeSection.id === 'pompeia' || activeSection.id === 'scavino') {
            let overallFoundResults = false;
            let firstMatchElement = null;
            const eventsInActiveSection = activeSection.querySelectorAll('.timeline-event');
            if (eventsInActiveSection.length === 0 && normalizedSearchTerm && noResultsMessageTimeline) {
                 noResultsMessageTimeline.style.display = 'block'; return;
            }
            eventsInActiveSection.forEach(eventDiv => {
                const titleElement = eventDiv.querySelector('.event-title');
                const detailsElement = eventDiv.querySelector('.event-details');
                const contentPElement = detailsElement?.querySelector('p.event-text-content');
                if (titleElement && titleElement.dataset.originalHtml) titleElement.innerHTML = titleElement.dataset.originalHtml;
                if (contentPElement && contentPElement.dataset.originalHtml) contentPElement.innerHTML = contentPElement.dataset.originalHtml;
                let eventTextContent = `${eventDiv.dataset.year || ''} ${titleElement?.textContent || ''} ${contentPElement?.textContent || ''}`.toLowerCase();
                if (normalizedSearchTerm === '') {
                    eventDiv.style.display = '';
                    if (detailsElement && detailsElement.classList.contains('open')) { /* Mantém aberto se já estava */ }
                    else if (detailsElement) { detailsElement.classList.remove('open'); detailsDiv.style.maxHeight = '0px';}
                    overallFoundResults = true;
                } else if (eventTextContent.includes(normalizedSearchTerm)) {
                    eventDiv.style.display = '';
                    if (detailsElement) {
                        detailsElement.classList.add('open');
                        detailsElement.style.maxHeight = detailsElement.scrollHeight + "px";
                    }
                    overallFoundResults = true;
                    if (!firstMatchElement) firstMatchElement = eventDiv;
                    const regex = new RegExp(normalizedSearchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
                    if (titleElement && titleElement.dataset.originalHtml) titleElement.innerHTML = titleElement.dataset.originalHtml.replace(regex, `<span class="search-highlight">$&</span>`);
                    if (contentPElement && contentPElement.dataset.originalHtml) contentPElement.innerHTML = contentPElement.dataset.originalHtml.replace(regex, `<span class="search-highlight">$&</span>`);
                } else {
                    eventDiv.style.display = 'none';
                    if (detailsElement) {detailsElement.classList.remove('open'); detailsDiv.style.maxHeight = '0px';}
                }
            });
            if (noResultsMessageTimeline && normalizedSearchTerm !== '' && !overallFoundResults) noResultsMessageTimeline.style.display = 'block';
            if (firstMatchElement) setTimeout(() => firstMatchElement.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100);
        } else if (activeSection.id === 'gallery') {
            renderGalleryWithContextualTopics(allGalleryImagesData);
        }
    }

    if (searchBar) searchBar.addEventListener('keydown', (event) => { if (event.key === 'Enter') performSearch(searchBar.value); });
    if (executeSearchButton) executeSearchButton.addEventListener('click', () => { if (searchBar) performSearch(searchBar.value); });
    if (clearSearchButton) clearSearchButton.addEventListener('click', () => { if (searchBar) searchBar.value = ''; activeGalleryTags.clear(); document.querySelectorAll('#gallery-tags .tag-filter-button.active').forEach(btn => {btn.classList.remove('active'); btn.setAttribute('aria-pressed','false');}); if(clearGalleryTagsFilterButton) clearGalleryTagsFilterButton.style.display = 'none'; performSearch(''); });
    
    let scrollTimeout;
    window.addEventListener('scroll', function() {
        if (scrollTimeout) window.cancelAnimationFrame(scrollTimeout);
        scrollTimeout = window.requestAnimationFrame(function() {
            const currentScrollY = window.scrollY;
            if (stickyHeaderNavWrapper && stickyHeaderNavWrapper.offsetHeight) {
                const headerHeight = stickyHeaderNavWrapper.offsetHeight;
                if (currentScrollY > lastScrollY && currentScrollY > (headerHeight + 50) ) {
                    stickyHeaderNavWrapper.classList.add('-translate-y-full');
                } else if (currentScrollY < lastScrollY || currentScrollY <= headerHeight + 50) {
                    stickyHeaderNavWrapper.classList.remove('-translate-y-full');
                }
            }
            lastScrollY = currentScrollY <= 0 ? 0 : currentScrollY;
        });
    }, false);

    showSection('intro');
});