const API_BASE_URL = 'http://127.0.0.1:8000';

const fileInput = document.getElementById('file-input');
const uploadButton = document.getElementById('upload-button');
const uploadStatus = document.getElementById('upload-status');
const uploadSection = document.getElementById('upload-section');
const searchSection = document.getElementById('search-section');
const searchInput = document.getElementById('search-input');
const searchButton = document.getElementById('search-button');
const searchStatus = document.getElementById('search-status');
const metadataSection = document.getElementById('metadata-section');
const documentSection = document.getElementById('document-section');
const documentDisplay = document.getElementById('document-display');
const documentTitle = document.getElementById('document-title');
const documentSubtitle = document.getElementById('document-subtitle');
const selectedFileEl = document.getElementById('selected-file');
const dropZone = document.getElementById('drop-zone');
const themeToggleBtn = document.getElementById('theme-toggle');

let uploadedDocumentText = '';
let currentHighlights = [];
let uploadedFileName = '';

document.addEventListener('DOMContentLoaded', () => {
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }
    if (dropZone) {
        ;['dragenter','dragover'].forEach(evt => {
            dropZone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('drag-over');
            });
        });
        ;['dragleave','drop'].forEach(evt => {
            dropZone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('drag-over');
            });
        });
        dropZone.addEventListener('drop', (e) => {
            const files = e.dataTransfer && e.dataTransfer.files;
            const file = files && files[0];
            if (file) {
                processSelectedFile(file);
                try {
                    const dt = new DataTransfer();
                    dt.items.add(file);
                    fileInput.files = dt.files;
                } catch (_) { }
            }
        });
    }
    
    if (uploadButton) {
        uploadButton.addEventListener('click', handleUpload);
    }
    
    if (searchButton) {
        searchButton.addEventListener('click', handleSearch);
    }
    
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleSearch();
            }
        });
    }

    if (themeToggleBtn) {
        const root = document.documentElement;
        const saved = localStorage.getItem('theme');
        if (saved === 'light' || saved === 'dark') {
            root.setAttribute('data-theme', saved);
        }
        updateThemeToggleLabel();
        themeToggleBtn.addEventListener('click', () => {
            const current = root.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
            const next = current === 'light' ? 'dark' : 'light';
            root.setAttribute('data-theme', next);
            try { localStorage.setItem('theme', next); } catch (_) {}
            updateThemeToggleLabel();
        });
    }
});

function setTextById(id, text) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = text;
    }
    return el;
}

function setDocumentHeader(title, subtitle) {
    if (documentTitle) {
        documentTitle.textContent = title;
    }
    if (documentSubtitle) {
        documentSubtitle.textContent = subtitle;
    }
}

function updateThemeToggleLabel() {
    if (!themeToggleBtn) return;
    const theme = (document.documentElement.getAttribute('data-theme') === 'light') ? 'Light' : 'Dark';
    themeToggleBtn.textContent = theme;
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        processSelectedFile(file);
    }
}

function processSelectedFile(file) {
    const lowerName = file.name.toLowerCase();
    const allowed = ['.txt', '.pdf', '.doc', '.docx'];
    const isAllowed = allowed.some(ext => lowerName.endsWith(ext));
    if (!isAllowed) {
        showStatus(uploadStatus, 'Please select a .txt, .pdf, .doc, or .docx file', 'error');
        if (uploadButton) {
            uploadButton.disabled = true;
        }
        if (selectedFileEl) {
            selectedFileEl.hidden = true;
            selectedFileEl.textContent = '';
        }
        return;
    }

    uploadedFileName = file.name;
    if (uploadButton) {
        uploadButton.disabled = false;
    }
    uploadedDocumentText = '';
    if (documentSection) {
        documentSection.hidden = true;
    }
    if (metadataSection) {
        metadataSection.hidden = true;
    }
    if (searchSection) {
        searchSection.hidden = true;
    }
    setDocumentHeader('Document Content', 'Upload a TXT, PDF or Word file to preview and search.');
    if (selectedFileEl) {
        selectedFileEl.textContent = `Selected: ${file.name}`;
        selectedFileEl.hidden = false;
    }
    showStatus(uploadStatus, `Selected: ${file.name} (preview after upload)`, 'info');
}

async function handleUpload() {
    const file = fileInput.files[0];
    if (!file) {
        showStatus(uploadStatus, 'Please select a file first', 'error');
        return;
    }

    uploadedFileName = file.name;
    if (uploadButton) {
        uploadButton.disabled = true;
    }
    showStatus(uploadStatus, 'Uploading...', 'info');
    if (documentSection) {
        documentSection.hidden = true;
    }
    if (metadataSection) {
        metadataSection.hidden = true;
    }
    if (searchSection) {
        searchSection.hidden = true;
    }

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Upload failed with status ${response.status}`);
        }

        const data = await response.json();
        const extractionStatus = (data && typeof data.extraction_status === 'string') ? data.extraction_status : '';
        
        showStatus(uploadStatus, 
            `Document uploaded successfully. Length: ${data.doc_length} characters, Unique terms: ${data.unique_terms}${extractionStatus ? `. ${extractionStatus}` : ''}`, 
            'success'
        );

        if (searchSection) {
            searchSection.hidden = false;
        }
        if (searchInput) {
            searchInput.focus();
        }

        uploadedDocumentText = data.text || '';
        if (documentDisplay) {
            documentDisplay.textContent = uploadedDocumentText;
        }
        if (documentSection) {
            documentSection.hidden = false;
        }
        currentHighlights = [];
        const ext = (file.name.split('.').pop() || '').toLowerCase();
        const subtitlePieces = [];
        if (extractionStatus) {
            subtitlePieces.push(extractionStatus);
        } else if (ext === 'pdf') {
            subtitlePieces.push('PDF extracted for preview and search.');
        } else {
            subtitlePieces.push('Document extracted for preview and search.');
        }
        subtitlePieces.push('Search highlights matched terms in this content.');
        setDocumentHeader(uploadedFileName || 'Document Content', subtitlePieces.join(' — '));

    } catch (error) {
        console.error('Upload error:', error);
        showStatus(uploadStatus, `Upload failed: ${error.message}`, 'error');
        uploadedDocumentText = '';
        currentHighlights = [];
        if (documentDisplay) {
            documentDisplay.textContent = '';
        }
        setDocumentHeader('Document Content', 'Upload a text-based TXT, PDF or .docx file to preview and search.');
        if (uploadButton) {
            uploadButton.disabled = false;
        }
    }
}

async function handleSearch() {
    const query = searchInput.value.trim();
    
    if (!query) {
        showStatus(searchStatus, 'Please enter a search query', 'error');
        return;
    }

    if (!uploadedDocumentText) {
        showStatus(searchStatus, 'Please upload a document first', 'error');
        return;
    }

    if (searchButton) {
        searchButton.disabled = true;
    }
    showStatus(searchStatus, 'Searching...', 'info');
    if (metadataSection) {
        metadataSection.hidden = true;
    }

    try {
        const searchUrl = new URL(`${API_BASE_URL}/search`);
        searchUrl.searchParams.set('q', query);

        const response = await fetch(searchUrl.toString(), {
            method: 'GET'
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Search failed with status ${response.status}`);
        }

        const data = await response.json();

        updateMetadata(data);

        highlightDocument(data.matches, query);

        if (metadataSection) {
            metadataSection.hidden = false;
        }

        if (data.total_matches === 0) {
            showStatus(searchStatus, 'No matches found', 'info');
        } else {
            searchStatus.hidden = true;
        }

    } catch (error) {
        console.error('Search error:', error);
        showStatus(searchStatus, `Search failed: ${error.message}`, 'error');
    } finally {
        if (searchButton) {
            searchButton.disabled = false;
        }
    }
}

function updateMetadata(data) {
    setTextById('total-matches', String(data.total_matches || 0));
    const t = parseFloat(data.time_ms);
    const ms = Number.isFinite(t) ? t : 0;
    const formatted = (ms < 1 && ms > 0) ? ms.toFixed(3) : ms.toFixed(3);
    setTextById('time-taken', `${formatted} ms`);
    
    const cacheStatus = data.cache || 'UNKNOWN';
    const cacheElement = setTextById('cache-status', cacheStatus);
    if (cacheElement) {
        cacheElement.classList.add('subtle');
        cacheElement.style.color = '';
    }
}

function highlightDocument(matches, query) {
    if (!matches || matches.length === 0) {
        if (documentDisplay) {
            documentDisplay.textContent = uploadedDocumentText;
        }
        currentHighlights = [];
        return;
    }

    const highlightRanges = [];
    const textLength = uploadedDocumentText.length;
    
    matches.forEach(match => {
        if (match.term && match.positions && Array.isArray(match.positions)) {
            const termLength = match.term.length;
            match.positions.forEach(pos => {
                const start = parseInt(pos);
                if (!Number.isFinite(start)) {
                    return;
                }
                const safeStart = Math.max(0, Math.min(start, textLength));
                const safeEnd = Math.max(safeStart, Math.min(safeStart + termLength, textLength));
                if (safeEnd > safeStart) {
                    highlightRanges.push({ start: safeStart, end: safeEnd, term: match.term });
                }
            });
        }
    });

    if (highlightRanges.length === 0) {
        highlightByTerms(matches, query);
        return;
    }

    highlightRanges.sort((a, b) => a.start - b.start);
    
    const mergedRanges = [];
    for (const range of highlightRanges) {
        if (mergedRanges.length === 0) {
            mergedRanges.push(range);
        } else {
            const last = mergedRanges[mergedRanges.length - 1];
            if (range.start <= last.end) {
                last.end = Math.max(last.end, range.end);
            } else {
                mergedRanges.push(range);
            }
        }
    }

    let highlightedHTML = '';
    let currentPos = 0;
    const text = uploadedDocumentText;
    
    mergedRanges.forEach(range => {
        if (currentPos < range.start) {
            highlightedHTML += escapeHtml(text.substring(currentPos, range.start));
        }
        
        const highlightedText = text.substring(range.start, Math.min(range.end, text.length));
        highlightedHTML += `<mark class="highlight">${escapeHtml(highlightedText)}</mark>`;
        
        currentPos = range.end;
    });
    
    if (currentPos < text.length) {
        highlightedHTML += escapeHtml(text.substring(currentPos));
    }

    if (documentDisplay) {
        documentDisplay.innerHTML = highlightedHTML;
    }
    currentHighlights = mergedRanges;
}

function highlightByTerms(matches, query) {
    const terms = query.toLowerCase().split(/\s+/).filter(t => t.length > 0);
    let highlightedHTML = escapeHtml(uploadedDocumentText);
    
    terms.forEach(term => {
        const regex = new RegExp(`(${escapeRegex(term)})`, 'gi');
        highlightedHTML = highlightedHTML.replace(regex, '<mark class="highlight">$1</mark>');
    });
    
    if (documentDisplay) {
        documentDisplay.innerHTML = highlightedHTML;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function showStatus(element, message, type) {
    element.textContent = message;
    element.className = `status-message ${type}`;
    element.hidden = false;
}
