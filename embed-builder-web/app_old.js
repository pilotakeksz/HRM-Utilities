// Discohook-style Embed Builder
class EmbedBuilder {
    constructor() {
        this.messages = []; // Changed from embeds to messages
        this.currentMessageIndex = 0;
        this.currentEmbedIndex = 0;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.addMessage();
        this.render();
        this.loadSavedMessages();
    }

    setupEventListeners() {
        // Header buttons
        document.getElementById('import-btn').addEventListener('click', () => this.openImportModal());
        document.getElementById('export-json-btn').addEventListener('click', () => this.exportCompleteJSON());
        document.getElementById('copy-json-btn').addEventListener('click', () => this.openCopyJSONModal());
        document.getElementById('send-btn').addEventListener('click', () => this.openWebhookModal());

        // Sidebar buttons
        document.getElementById('add-embed-btn').addEventListener('click', () => this.addMessage());

        // Editor buttons
        document.getElementById('duplicate-embed-btn').addEventListener('click', () => this.duplicateEmbed());
        document.getElementById('delete-embed-btn').addEventListener('click', () => this.deleteEmbed());
        document.getElementById('add-field-btn').addEventListener('click', () => this.addField());
        document.getElementById('add-button-btn').addEventListener('click', () => this.addAction('button'));
        document.getElementById('add-select-btn').addEventListener('click', () => this.addAction('select'));

        // Form inputs
        this.setupFormInputs();

        // Modal events
        this.setupModalEvents();

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
    }

    setupFormInputs() {
        const inputs = [
            'embed-title', 'embed-description', 'embed-color', 'embed-url',
            'author-name', 'author-url', 'author-icon',
            'thumbnail-url', 'image-url',
            'footer-text', 'footer-icon'
        ];

        inputs.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('input', () => this.updateCurrentEmbed());
            }
        });

        // Color picker sync
        const colorInput = document.getElementById('embed-color');
        const colorPicker = document.getElementById('embed-color-picker');
        
        colorInput.addEventListener('input', () => {
            const value = colorInput.value.replace('#', '');
            if (/^[0-9A-Fa-f]{6}$/.test(value)) {
                colorPicker.value = '#' + value;
            }
        });

        colorPicker.addEventListener('input', () => {
            colorInput.value = colorPicker.value.replace('#', '');
            this.updateCurrentEmbed();
        });
    }

    setupModalEvents() {
        // Import modal
        document.getElementById('import-modal-close').addEventListener('click', () => this.closeModal('import-modal'));
        document.getElementById('import-cancel-btn').addEventListener('click', () => this.closeModal('import-modal'));
        document.getElementById('import-confirm-btn').addEventListener('click', () => this.importJSON());

        // Webhook modal
        document.getElementById('webhook-modal-close').addEventListener('click', () => this.closeModal('webhook-modal'));
        document.getElementById('webhook-cancel-btn').addEventListener('click', () => this.closeModal('webhook-modal'));
        document.getElementById('webhook-send-btn').addEventListener('click', () => this.sendWebhook());

        // Copy JSON modal
        document.getElementById('copy-json-modal-close').addEventListener('click', () => this.closeModal('copy-json-modal'));
        document.getElementById('copy-json-cancel-btn').addEventListener('click', () => this.closeModal('copy-json-modal'));
        document.getElementById('copy-json-copy-btn').addEventListener('click', () => this.copyJSONToClipboard());

        // Close modals on backdrop click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modal.id);
                }
            });
        });
    }

    handleKeyboard(e) {
        if (e.ctrlKey || e.metaKey) {
            switch (e.key) {
                case 's':
                    e.preventDefault();
                    this.saveCurrentEmbed();
                    break;
                case 'n':
                    e.preventDefault();
                    this.addMessage();
                    break;
                case 'd':
                    e.preventDefault();
                    this.duplicateEmbed();
                    break;
            }
        }

        if (e.key === 'Delete' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
            this.deleteEmbed();
        }
    }

    addMessage() {
        const newMessage = {
            embeds: [{
                title: '',
                description: '',
                color: '7289da',
                url: '',
                author: {
                    name: '',
                    url: '',
                    icon_url: ''
                },
                thumbnail: {
                    url: ''
                },
                image: {
                    url: ''
                },
                fields: [],
                footer: {
                    text: '',
                    icon_url: ''
                },
                actions: []
            }]
        };

        this.messages.push(newMessage);
        this.currentMessageIndex = this.messages.length - 1;
        this.currentEmbedIndex = 0;
        this.render();
    }

    addEmbed() {
        if (this.messages.length === 0) {
            this.addMessage();
            return;
        }

        const newEmbed = {
            title: '',
            description: '',
            color: '7289da',
            url: '',
            author: {
                name: '',
                url: '',
                icon_url: ''
            },
            thumbnail: {
                url: ''
            },
            image: {
                url: ''
            },
            fields: [],
            footer: {
                text: '',
                icon_url: ''
            },
            actions: []
        };

        this.messages[this.currentMessageIndex].embeds.push(newEmbed);
        this.currentEmbedIndex = this.messages[this.currentMessageIndex].embeds.length - 1;
        this.render();
    }

    duplicateEmbed() {
        if (this.messages.length === 0) return;
        
        const currentMessage = this.messages[this.currentMessageIndex];
        const currentEmbed = JSON.parse(JSON.stringify(currentMessage.embeds[this.currentEmbedIndex]));
        currentMessage.embeds.splice(this.currentEmbedIndex + 1, 0, currentEmbed);
        this.currentEmbedIndex++;
        this.render();
    }

    deleteEmbed() {
        if (this.messages.length === 0) return;
        
        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length <= 1) return;
        
        currentMessage.embeds.splice(this.currentEmbedIndex, 1);
        if (this.currentEmbedIndex >= currentMessage.embeds.length) {
            this.currentEmbedIndex = currentMessage.embeds.length - 1;
        }
        this.render();
    }

    deleteMessage() {
        if (this.messages.length <= 1) return;
        
        this.messages.splice(this.currentMessageIndex, 1);
        if (this.currentMessageIndex >= this.messages.length) {
            this.currentMessageIndex = this.messages.length - 1;
        }
        this.currentEmbedIndex = 0;
        this.render();
    }

    setCurrentMessage(index) {
        this.currentMessageIndex = index;
        this.currentEmbedIndex = 0;
        this.render();
    }

    setCurrentEmbed(index) {
        this.currentEmbedIndex = index;
        this.render();
    }

    updateCurrentEmbed() {
        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        const embed = currentMessage.embeds[this.currentEmbedIndex];
        
        embed.title = document.getElementById('embed-title').value;
        embed.description = document.getElementById('embed-description').value;
        embed.color = document.getElementById('embed-color').value.replace('#', '');
        embed.url = document.getElementById('embed-url').value;
        
        embed.author.name = document.getElementById('author-name').value;
        embed.author.url = document.getElementById('author-url').value;
        embed.author.icon_url = document.getElementById('author-icon').value;
        
        embed.thumbnail.url = document.getElementById('thumbnail-url').value;
        embed.image.url = document.getElementById('image-url').value;
        
        embed.footer.text = document.getElementById('footer-text').value;
        embed.footer.icon_url = document.getElementById('footer-icon').value;

        this.renderPreview();
        this.renderEmbedList();
    }

    addField() {
        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        const field = {
            name: '',
            value: '',
            inline: false
        };

        currentMessage.embeds[this.currentEmbedIndex].fields.push(field);
        this.renderFields();
        this.renderPreview();
    }

    updateField(fieldIndex, property, value) {
        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        const field = currentMessage.embeds[this.currentEmbedIndex].fields[fieldIndex];
        if (property === 'inline') {
            field[property] = value === 'true';
        } else {
            field[property] = value;
        }

        this.renderPreview();
    }

    deleteField(fieldIndex) {
        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        currentMessage.embeds[this.currentEmbedIndex].fields.splice(fieldIndex, 1);
        this.renderFields();
        this.renderPreview();
    }

    addAction(type) {
        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        const action = {
            type: type,
            label: '',
            url: '',
            target: '',
            ephemeral: false,
            placeholder: '',
            options: [],
            buttonType: 'link' // Default button type
        };

        currentMessage.embeds[this.currentEmbedIndex].actions.push(action);
        this.renderActions();
        this.renderPreview();
    }

    updateAction(actionIndex, property, value) {
        if (this.embeds.length === 0) return;

        const action = this.embeds[this.currentEmbedIndex].actions[actionIndex];
        if (property === 'ephemeral') {
            action[property] = value === 'true';
        } else if (property === 'buttonType') {
            action[property] = value;
            // Show/hide appropriate inputs based on button type
            this.renderActions();
            return; // Don't call renderPreview here as renderActions will handle it
        } else {
            action[property] = value;
        }

        this.renderPreview();
    }

    deleteAction(actionIndex) {
        if (this.embeds.length === 0) return;

        this.embeds[this.currentEmbedIndex].actions.splice(actionIndex, 1);
        this.renderActions();
        this.renderPreview();
    }

    addActionOption(actionIndex) {
        if (this.embeds.length === 0) return;

        const option = {
            label: '',
            value: '',
            description: '',
            icon: ''
        };

        this.embeds[this.currentEmbedIndex].actions[actionIndex].options.push(option);
        this.renderActions();
    }

    addSavedEmbedOption(actionIndex, optionIndex) {
        const savedEmbeds = this.getSavedEmbeds();
        if (savedEmbeds.length === 0) {
            alert('No saved embeds available');
            return;
        }

        // Create a modal for embed selection
        this.createEmbedSelectionModal(savedEmbeds, (selectedKey) => {
            if (!selectedKey) return;

            const selectedEmbed = savedEmbeds.find(embed => embed.key === selectedKey);
            if (!selectedEmbed) {
                alert('Embed not found');
                return;
            }

            // Update the option with the saved embed reference
            this.embeds[this.currentEmbedIndex].actions[actionIndex].options[optionIndex].label = selectedKey;
            this.embeds[this.currentEmbedIndex].actions[actionIndex].options[optionIndex].value = `send:${selectedKey}`;
            this.embeds[this.currentEmbedIndex].actions[actionIndex].options[optionIndex].description = `Send saved embed: ${selectedKey}`;
            
            this.renderActions();
            this.renderPreview();
        });
    }

    addSavedEmbedToButton(actionIndex) {
        const savedEmbeds = this.getSavedEmbeds();
        if (savedEmbeds.length === 0) {
            alert('No saved embeds available');
            return;
        }

        // Create a modal for embed selection
        this.createEmbedSelectionModal(savedEmbeds, (selectedKey) => {
            if (!selectedKey) return;

            const selectedEmbed = savedEmbeds.find(embed => embed.key === selectedKey);
            if (!selectedEmbed) {
                alert('Embed not found');
                return;
            }

            // Update the button with the saved embed reference
            this.embeds[this.currentEmbedIndex].actions[actionIndex].target = `send:${selectedKey}`;
            this.renderActions();
            this.renderPreview();
        });
    }

    createEmbedSelectionModal(savedEmbeds, callback) {
        // Create modal overlay
        const modal = document.createElement('div');
        modal.className = 'modal active';
        modal.style.zIndex = '2000';

        // Create modal content
        const modalContent = document.createElement('div');
        modalContent.className = 'modal-content';
        modalContent.style.maxWidth = '600px';

        // Create header
        const header = document.createElement('div');
        header.className = 'modal-header';
        header.innerHTML = `
            <h2>Select Saved Embed</h2>
            <button class="modal-close" id="embed-selection-close">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;

        // Create body with embed list
        const body = document.createElement('div');
        body.className = 'modal-body';
        body.style.maxHeight = '400px';
        body.style.overflowY = 'auto';

        const embedList = document.createElement('div');
        embedList.className = 'embed-selection-list';
        embedList.style.display = 'flex';
        embedList.style.flexDirection = 'column';
        embedList.style.gap = '0.5rem';

        savedEmbeds.forEach(embed => {
            const embedItem = document.createElement('div');
            embedItem.className = 'embed-selection-item';
            embedItem.style.display = 'flex';
            embedItem.style.alignItems = 'center';
            embedItem.style.gap = '1rem';
            embedItem.style.padding = '1rem';
            embedItem.style.border = '1px solid var(--border)';
            embedItem.style.borderRadius = '8px';
            embedItem.style.cursor = 'pointer';
            embedItem.style.transition = 'all 0.2s ease';

            embedItem.addEventListener('mouseenter', () => {
                embedItem.style.background = 'var(--background-tertiary)';
                embedItem.style.borderColor = 'var(--primary)';
            });

            embedItem.addEventListener('mouseleave', () => {
                embedItem.style.background = 'transparent';
                embedItem.style.borderColor = 'var(--border)';
            });

            embedItem.addEventListener('click', () => {
                callback(embed.key);
                document.body.removeChild(modal);
            });

            const embedInfo = document.createElement('div');
            embedInfo.style.flex = '1';

            const embedName = document.createElement('div');
            embedName.style.fontWeight = '600';
            embedName.style.color = 'var(--text-primary)';
            embedName.style.marginBottom = '0.25rem';
            embedName.textContent = embed.key;

            const embedPreview = document.createElement('div');
            embedPreview.style.fontSize = '0.875rem';
            embedPreview.style.color = 'var(--text-secondary)';
            embedPreview.textContent = embed.data.embed?.title || embed.data.embed?.description || 'No title or description';

            embedInfo.appendChild(embedName);
            embedInfo.appendChild(embedPreview);
            embedItem.appendChild(embedInfo);

            embedList.appendChild(embedItem);
        });

        body.appendChild(embedList);

        // Create footer
        const footer = document.createElement('div');
        footer.className = 'modal-footer';
        footer.innerHTML = `
            <button class="btn btn-secondary" id="embed-selection-cancel">Cancel</button>
        `;

        modalContent.appendChild(header);
        modalContent.appendChild(body);
        modalContent.appendChild(footer);
        modal.appendChild(modalContent);
        document.body.appendChild(modal);

        // Add event listeners
        document.getElementById('embed-selection-close').addEventListener('click', () => {
            document.body.removeChild(modal);
        });

        document.getElementById('embed-selection-cancel').addEventListener('click', () => {
            document.body.removeChild(modal);
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        });
    }

    getSavedEmbeds() {
        const savedEmbeds = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith('embed_')) {
                try {
                    const data = JSON.parse(localStorage.getItem(key));
                    savedEmbeds.push({ key: key.replace('embed_', ''), data });
                } catch (e) {
                    // Skip invalid entries
                }
            }
        }
        return savedEmbeds;
    }

    updateActionOption(actionIndex, optionIndex, property, value) {
        if (this.embeds.length === 0) return;

        const option = this.embeds[this.currentEmbedIndex].actions[actionIndex].options[optionIndex];
        option[property] = value;
        this.renderPreview();
    }

    deleteActionOption(actionIndex, optionIndex) {
        if (this.embeds.length === 0) return;

        this.embeds[this.currentEmbedIndex].actions[actionIndex].options.splice(optionIndex, 1);
        this.renderActions();
    }

    render() {
        this.renderEmbedList();
        this.renderForm();
        this.renderPreview();
        this.updateCounter();
    }

    renderEmbedList() {
        const container = document.getElementById('embed-list');
        container.innerHTML = '';

        this.embeds.forEach((embed, index) => {
            const item = document.createElement('div');
            item.className = `embed-item ${index === this.currentEmbedIndex ? 'active' : ''}`;

            const leftSection = document.createElement('div');
            leftSection.className = 'embed-item-left';
            leftSection.addEventListener('click', () => this.setCurrentEmbed(index));

            const number = document.createElement('div');
            number.className = 'embed-number';
            number.textContent = index + 1;

            const title = document.createElement('div');
            title.className = 'embed-title';
            title.textContent = embed.title || `Embed ${index + 1}`;

            leftSection.appendChild(number);
            leftSection.appendChild(title);

            const saveBtn = document.createElement('button');
            saveBtn.className = 'btn btn-sm btn-secondary embed-save-btn';
            saveBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17,21 17,13 7,13 7,21"></polyline><polyline points="7,3 7,8 15,8"></polyline></svg>';
            saveBtn.title = 'Save this embed';
            saveBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.saveCurrentEmbed(index);
            });

            item.appendChild(leftSection);
            item.appendChild(saveBtn);
            container.appendChild(item);
        });
    }

    renderForm() {
        if (this.embeds.length === 0) return;

        const embed = this.embeds[this.currentEmbedIndex];

        document.getElementById('embed-title').value = embed.title || '';
        document.getElementById('embed-description').value = embed.description || '';
        document.getElementById('embed-color').value = embed.color || '';
        document.getElementById('embed-url').value = embed.url || '';
        
        document.getElementById('author-name').value = embed.author.name || '';
        document.getElementById('author-url').value = embed.author.url || '';
        document.getElementById('author-icon').value = embed.author.icon_url || '';
        
        document.getElementById('thumbnail-url').value = embed.thumbnail.url || '';
        document.getElementById('image-url').value = embed.image.url || '';
        
        document.getElementById('footer-text').value = embed.footer.text || '';
        document.getElementById('footer-icon').value = embed.footer.icon_url || '';

        // Update color picker
        const colorValue = embed.color || '7289da';
        document.getElementById('embed-color-picker').value = '#' + colorValue;

        this.renderFields();
        this.renderActions();
    }

    renderFields() {
        const container = document.getElementById('fields-list');
        container.innerHTML = '';

        if (this.embeds.length === 0) return;

        const fields = this.embeds[this.currentEmbedIndex].fields;

        fields.forEach((field, index) => {
            const fieldItem = document.createElement('div');
            fieldItem.className = 'field-item';

            const header = document.createElement('div');
            header.className = 'field-header';

            const title = document.createElement('div');
            title.className = 'field-title';
            title.textContent = `Field ${index + 1}`;

            const actions = document.createElement('div');
            actions.className = 'field-actions';

            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn btn-sm btn-danger';
            deleteBtn.innerHTML = '🗑';
            deleteBtn.addEventListener('click', () => this.deleteField(index));

            actions.appendChild(deleteBtn);
            header.appendChild(title);
            header.appendChild(actions);

            const content = document.createElement('div');
            content.className = 'field-content';

            const nameInput = document.createElement('input');
            nameInput.type = 'text';
            nameInput.className = 'form-input';
            nameInput.placeholder = 'Field name';
            nameInput.value = field.name;
            nameInput.addEventListener('input', (e) => this.updateField(index, 'name', e.target.value));

            const valueInput = document.createElement('textarea');
            valueInput.className = 'form-textarea';
            valueInput.placeholder = 'Field value';
            valueInput.value = field.value;
            valueInput.rows = 2;
            valueInput.addEventListener('input', (e) => this.updateField(index, 'value', e.target.value));

            const inlineSelect = document.createElement('select');
            inlineSelect.className = 'form-input';
            inlineSelect.innerHTML = `
                <option value="false">Block</option>
                <option value="true">Inline</option>
            `;
            inlineSelect.value = field.inline.toString();
            inlineSelect.addEventListener('change', (e) => this.updateField(index, 'inline', e.target.value));

            content.appendChild(nameInput);
            content.appendChild(valueInput);
            content.appendChild(inlineSelect);

            fieldItem.appendChild(header);
            fieldItem.appendChild(content);
            container.appendChild(fieldItem);
        });
    }

    renderActions() {
        const container = document.getElementById('actions-list');
        container.innerHTML = '';

        if (this.embeds.length === 0) return;

        const actions = this.embeds[this.currentEmbedIndex].actions;

        actions.forEach((action, actionIndex) => {
            const actionItem = document.createElement('div');
            actionItem.className = 'action-item';

            const header = document.createElement('div');
            header.className = 'action-header';

            const type = document.createElement('div');
            type.className = 'action-type';
            type.textContent = action.type === 'button' ? 'Button' : 'Select Menu';

            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'field-actions';

            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn btn-sm btn-danger';
            deleteBtn.innerHTML = '🗑';
            deleteBtn.addEventListener('click', () => this.deleteAction(actionIndex));

            actionsDiv.appendChild(deleteBtn);
            header.appendChild(type);
            header.appendChild(actionsDiv);

            const content = document.createElement('div');
            content.className = 'action-content';

            if (action.type === 'button') {
                const labelInput = document.createElement('input');
                labelInput.type = 'text';
                labelInput.className = 'form-input';
                labelInput.placeholder = 'Button label';
                labelInput.value = action.label;
                labelInput.addEventListener('input', (e) => this.updateAction(actionIndex, 'label', e.target.value));

                // Button type selector
                const typeSelect = document.createElement('select');
                typeSelect.className = 'form-input';
                typeSelect.innerHTML = `
                    <option value="link" ${action.buttonType === 'link' ? 'selected' : ''}>Link Button</option>
                    <option value="send_embed" ${action.buttonType === 'send_embed' ? 'selected' : ''}>Send Embed</option>
                `;
                typeSelect.addEventListener('change', (e) => this.updateAction(actionIndex, 'buttonType', e.target.value));

                const urlInput = document.createElement('input');
                urlInput.type = 'url';
                urlInput.className = 'form-input';
                urlInput.placeholder = 'Button URL';
                urlInput.value = action.url || '';
                urlInput.style.display = action.buttonType === 'link' ? 'block' : 'none';
                urlInput.addEventListener('input', (e) => this.updateAction(actionIndex, 'url', e.target.value));

                // Embed selection for send_embed type
                const embedSelect = document.createElement('div');
                embedSelect.className = 'embed-select-container';
                embedSelect.style.display = action.buttonType === 'send_embed' ? 'block' : 'none';

                const embedSelectInput = document.createElement('input');
                embedSelectInput.type = 'text';
                embedSelectInput.className = 'form-input';
                embedSelectInput.placeholder = 'Saved embed key or send_json:b64';
                embedSelectInput.value = action.target || '';
                embedSelectInput.addEventListener('input', (e) => this.updateAction(actionIndex, 'target', e.target.value));

                const useSavedEmbedBtn = document.createElement('button');
                useSavedEmbedBtn.className = 'btn btn-sm btn-primary';
                useSavedEmbedBtn.textContent = 'Use Saved Embed';
                useSavedEmbedBtn.addEventListener('click', () => this.addSavedEmbedToButton(actionIndex));

                embedSelect.appendChild(embedSelectInput);
                embedSelect.appendChild(useSavedEmbedBtn);

                content.appendChild(labelInput);
                content.appendChild(typeSelect);
                content.appendChild(urlInput);
                content.appendChild(embedSelect);
        } else {
                const placeholderInput = document.createElement('input');
                placeholderInput.type = 'text';
                placeholderInput.className = 'form-input';
                placeholderInput.placeholder = 'Select placeholder';
                placeholderInput.value = action.placeholder;
                placeholderInput.addEventListener('input', (e) => this.updateAction(actionIndex, 'placeholder', e.target.value));

                content.appendChild(placeholderInput);

                // Render options
                const optionsContainer = document.createElement('div');
                optionsContainer.className = 'options-container';
                optionsContainer.style.marginTop = '1rem';

                // Add options header with buttons
                const optionsHeader = document.createElement('div');
                optionsHeader.style.display = 'flex';
                optionsHeader.style.gap = '0.5rem';
                optionsHeader.style.marginBottom = '1rem';
                optionsHeader.style.alignItems = 'center';

                const addOptionBtn = document.createElement('button');
                addOptionBtn.className = 'btn btn-sm btn-secondary';
                addOptionBtn.textContent = 'Add Option';
                addOptionBtn.addEventListener('click', () => this.addActionOption(actionIndex));

                const addSavedEmbedBtn = document.createElement('button');
                addSavedEmbedBtn.className = 'btn btn-sm btn-primary';
                addSavedEmbedBtn.textContent = 'Add Saved Embed';
                addSavedEmbedBtn.addEventListener('click', () => {
                    const optionIndex = action.options.length;
                    this.addActionOption(actionIndex);
                    this.addSavedEmbedOption(actionIndex, optionIndex);
                });

                optionsHeader.appendChild(addOptionBtn);
                optionsHeader.appendChild(addSavedEmbedBtn);
                optionsContainer.appendChild(optionsHeader);

                action.options.forEach((option, optionIndex) => {
                    const optionItem = document.createElement('div');
                    optionItem.className = 'option-item';

                    // Create inputs container
                    const inputsContainer = document.createElement('div');
                    inputsContainer.className = 'option-inputs';

                    const labelInput = document.createElement('input');
                    labelInput.type = 'text';
                    labelInput.className = 'form-input';
                    labelInput.placeholder = 'Option label';
                    labelInput.value = option.label;
                    labelInput.addEventListener('input', (e) => this.updateActionOption(actionIndex, optionIndex, 'label', e.target.value));

                    const valueInput = document.createElement('input');
                    valueInput.type = 'text';
                    valueInput.className = 'form-input';
                    valueInput.placeholder = 'Option value (e.g., send:key, link:url)';
                    valueInput.value = option.value;
                    valueInput.addEventListener('input', (e) => this.updateActionOption(actionIndex, optionIndex, 'value', e.target.value));

                    inputsContainer.appendChild(labelInput);
                    inputsContainer.appendChild(valueInput);

                    // Create buttons container
                    const buttonsContainer = document.createElement('div');
                    buttonsContainer.className = 'option-buttons';

                    const useSavedBtn = document.createElement('button');
                    useSavedBtn.className = 'btn btn-sm btn-primary';
                    useSavedBtn.textContent = 'Use Saved';
                    useSavedBtn.title = 'Use a saved embed as this option';
                    useSavedBtn.addEventListener('click', () => this.addSavedEmbedOption(actionIndex, optionIndex));

                    const deleteOptionBtn = document.createElement('button');
                    deleteOptionBtn.className = 'btn btn-sm btn-danger';
                    deleteOptionBtn.innerHTML = '🗑';
                    deleteOptionBtn.addEventListener('click', () => this.deleteActionOption(actionIndex, optionIndex));

                    buttonsContainer.appendChild(useSavedBtn);
                    buttonsContainer.appendChild(deleteOptionBtn);

                    // Add description if value contains embed reference
                    if (option.value && (option.value.startsWith('send:') || option.value.startsWith('send_json:'))) {
                        const description = document.createElement('div');
                        description.className = 'option-description';
                        description.textContent = 'This option will send an embed';
                        optionItem.appendChild(description);
                    }

                    optionItem.appendChild(inputsContainer);
                    optionItem.appendChild(buttonsContainer);
                    optionsContainer.appendChild(optionItem);
                });

                content.appendChild(optionsContainer);
            }

            actionItem.appendChild(header);
            actionItem.appendChild(content);
            container.appendChild(actionItem);
        });
    }

    renderPreview() {
        const container = document.getElementById('preview-content');
        container.innerHTML = '';

        if (this.embeds.length === 0) return;

        const embed = this.embeds[this.currentEmbedIndex];
        const previewEmbed = document.createElement('div');
        previewEmbed.className = 'preview-embed';

        if (embed.title) {
            const title = document.createElement('div');
            title.className = 'preview-embed-title';
            title.textContent = embed.title;
            previewEmbed.appendChild(title);
        }

        if (embed.description) {
            const description = document.createElement('div');
            description.className = 'preview-embed-description';
            description.textContent = embed.description;
            previewEmbed.appendChild(description);
        }

        if (embed.fields && embed.fields.length > 0) {
            const fieldsContainer = document.createElement('div');
            fieldsContainer.className = 'preview-embed-fields';

            embed.fields.forEach(field => {
                const fieldDiv = document.createElement('div');
                fieldDiv.className = `preview-field ${field.inline ? 'inline' : ''}`;

                if (field.name) {
                    const name = document.createElement('div');
                    name.className = 'preview-field-name';
                    name.textContent = field.name;
                    fieldDiv.appendChild(name);
                }

                if (field.value) {
                    const value = document.createElement('div');
                    value.className = 'preview-field-value';
                    value.textContent = field.value;
                    fieldDiv.appendChild(value);
                }

                fieldsContainer.appendChild(fieldDiv);
            });

            previewEmbed.appendChild(fieldsContainer);
        }

        if (embed.footer.text) {
            const footer = document.createElement('div');
            footer.className = 'preview-embed-footer';

            if (embed.footer.icon_url) {
                const icon = document.createElement('img');
                icon.className = 'preview-footer-icon';
                icon.src = embed.footer.icon_url;
                icon.alt = 'Footer icon';
                footer.appendChild(icon);
            }

            const text = document.createElement('div');
            text.className = 'preview-footer-text';
            text.textContent = embed.footer.text;
            footer.appendChild(text);

            previewEmbed.appendChild(footer);
        }

        container.appendChild(previewEmbed);
    }

    updateCounter() {
        const counter = document.getElementById('embed-counter');
        counter.textContent = `Embed ${this.currentEmbedIndex + 1} of ${this.embeds.length}`;
    }

    openImportModal() {
        document.getElementById('import-modal').classList.add('active');
        document.getElementById('import-textarea').focus();
    }

    closeModal(modalId) {
        document.getElementById(modalId).classList.remove('active');
    }

    importJSON() {
        const textarea = document.getElementById('import-textarea');
        const jsonText = textarea.value.trim();

        if (!jsonText) {
            alert('Please enter JSON data');
      return;
    }

        try {
            const data = JSON.parse(jsonText);
            let embeds = [];

            if (Array.isArray(data)) {
                embeds = data;
            } else if (data.embeds && Array.isArray(data.embeds)) {
                embeds = data.embeds;
            } else {
                embeds = [data];
            }

            this.embeds = embeds.map(embed => ({
                title: embed.title || '',
                description: embed.description || '',
                color: embed.color ? embed.color.toString(16).padStart(6, '0') : '7289da',
                url: embed.url || '',
                author: {
                    name: embed.author?.name || '',
                    url: embed.author?.url || '',
                    icon_url: embed.author?.icon_url || ''
                },
                thumbnail: {
                    url: embed.thumbnail?.url || ''
                },
                image: {
                    url: embed.image?.url || ''
                },
                fields: (embed.fields || []).map(field => ({
                    name: field.name || '',
                    value: field.value || '',
                    inline: field.inline || false
                })),
                footer: {
                    text: embed.footer?.text || '',
                    icon_url: embed.footer?.icon_url || ''
                },
                actions: []
            }));

            this.currentEmbedIndex = 0;
            this.closeModal('import-modal');
            this.render();
            textarea.value = '';

        } catch (error) {
            alert('Invalid JSON: ' + error.message);
        }
    }

    openWebhookModal() {
        document.getElementById('webhook-modal').classList.add('active');
        document.getElementById('webhook-url').focus();
    }

    openCopyJSONModal() {
        // Generate the complete JSON data
        const payload = this.buildCompletePayload();
        const jsonString = JSON.stringify(payload, null, 2);
        
        // Display in the modal
        document.getElementById('json-code-content').textContent = jsonString;
        document.getElementById('copy-json-modal').classList.add('active');
    }

    buildCompletePayload() {
        // Collect all saved embeds that are referenced
        const referencedEmbeds = this.collectReferencedEmbeds();
        
        const payload = {
            embeds: this.embeds.map(embed => ({
                title: embed.title || undefined,
                description: embed.description || undefined,
                color: embed.color ? parseInt(embed.color, 16) : undefined,
                url: embed.url || undefined,
                author: embed.author.name ? {
                    name: embed.author.name,
                    url: embed.author.url || undefined,
                    icon_url: embed.author.icon_url || undefined
                } : undefined,
                thumbnail: embed.thumbnail.url ? {
                    url: embed.thumbnail.url
                } : undefined,
                image: embed.image.url ? {
                    url: embed.image.url
                } : undefined,
                fields: embed.fields.filter(field => field.name || field.value).map(field => ({
                    name: field.name || '\u200b',
                    value: field.value || '\u200b',
                    inline: field.inline
                })),
                footer: embed.footer.text ? {
                    text: embed.footer.text,
                    icon_url: embed.footer.icon_url || undefined
                } : undefined,
                // Include actions (buttons and select menus) with inlined embed data
                buttons: embed.actions.filter(action => action.type === 'button').map(button => {
                    if (button.buttonType === 'send_embed') {
                        return {
                            type: 'send_embed',
                            label: button.label,
                            target: button.target,
                            ephemeral: button.ephemeral || false
                        };
                    } else {
                        return {
                            type: 'link',
                            label: button.label,
                            url: button.url
                        };
                    }
                }),
                selects: embed.actions.filter(action => action.type === 'select').map(select => ({
                    placeholder: select.placeholder,
                    name: select.placeholder.toLowerCase().replace(/\s+/g, '_'),
                    options: select.options.map(option => {
                        const resolvedOption = { ...option };
                        
                        // If this option references a saved embed, inline the embed data
                        if (option.value && option.value.startsWith('send:')) {
                            const embedKey = option.value.substring(5); // Remove 'send:' prefix
                            const referencedEmbed = referencedEmbeds[embedKey];
                            if (referencedEmbed) {
                                resolvedOption.value = `send_json:${btoa(JSON.stringify(referencedEmbed))}`;
                            }
                        }
                        
                        return {
                            label: resolvedOption.label,
                            value: resolvedOption.value,
                            description: resolvedOption.description || '',
                            icon: resolvedOption.icon || ''
                        };
                    })
                }))
            })),
            // Include all referenced embeds as inlined data
            referenced_embeds: referencedEmbeds,
            // Include metadata
            metadata: {
                total_embeds: this.embeds.length,
                has_actions: this.embeds.some(embed => embed.actions.length > 0),
                has_buttons: this.embeds.some(embed => embed.actions.some(action => action.type === 'button')),
                has_selects: this.embeds.some(embed => embed.actions.some(action => action.type === 'select')),
                generated_at: new Date().toISOString(),
                version: '2.0'
            }
        };
        
        // Debug: Log the payload
        console.log('Generated payload:', payload);
        console.log('Number of embeds:', payload.embeds.length);
        
        return payload;
    }

    collectReferencedEmbeds() {
        const referencedEmbeds = {};
        
        // Find all references to saved embeds in select menu options
        this.embeds.forEach(embed => {
            embed.actions.forEach(action => {
                if (action.type === 'select') {
                    action.options.forEach(option => {
                        if (option.value && option.value.startsWith('send:')) {
                            const embedKey = option.value.substring(5); // Remove 'send:' prefix
                            
                            // Get the saved embed data from localStorage
                            const savedData = localStorage.getItem(`embed_${embedKey}`);
                            if (savedData) {
                                try {
                                    const parsed = JSON.parse(savedData);
                                    referencedEmbeds[embedKey] = parsed.embed;
                                } catch (e) {
                                    console.warn(`Failed to parse saved embed ${embedKey}:`, e);
                                }
                            }
                        }
                    });
                }
            });
        });
        
        return referencedEmbeds;
    }

    async copyJSONToClipboard() {
        const jsonString = document.getElementById('json-code-content').textContent;
        
        try {
            await navigator.clipboard.writeText(jsonString);
            
            // Show success feedback
            const copyBtn = document.getElementById('copy-json-copy-btn');
            const originalText = copyBtn.textContent;
            copyBtn.textContent = 'Copied!';
            copyBtn.style.background = 'var(--success)';
            
            setTimeout(() => {
                copyBtn.textContent = originalText;
                copyBtn.style.background = '';
            }, 2000);
            
        } catch (err) {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = jsonString;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            
            alert('JSON copied to clipboard!');
        }
    }

    async sendWebhook() {
        const url = document.getElementById('webhook-url').value.trim();
        const username = document.getElementById('webhook-username').value.trim();
        const avatar = document.getElementById('webhook-avatar').value.trim();

        if (!url) {
            alert('Please enter a webhook URL');
      return;
    }

        // Create comprehensive payload with all data including actions
        const payload = {
            embeds: this.embeds.map(embed => ({
                title: embed.title || undefined,
                description: embed.description || undefined,
                color: embed.color ? parseInt(embed.color, 16) : undefined,
                url: embed.url || undefined,
                author: embed.author.name ? {
                    name: embed.author.name,
                    url: embed.author.url || undefined,
                    icon_url: embed.author.icon_url || undefined
                } : undefined,
                thumbnail: embed.thumbnail.url ? {
                    url: embed.thumbnail.url
                } : undefined,
                image: embed.image.url ? {
                    url: embed.image.url
                } : undefined,
                fields: embed.fields.filter(field => field.name || field.value).map(field => ({
                    name: field.name || '\u200b',
                    value: field.value || '\u200b',
                    inline: field.inline
                })),
                footer: embed.footer.text ? {
                    text: embed.footer.text,
                    icon_url: embed.footer.icon_url || undefined
                } : undefined,
                // Include actions (buttons and select menus)
                buttons: embed.actions.filter(action => action.type === 'button').map(button => {
                    if (button.buttonType === 'send_embed') {
                        return {
                            type: 'send_embed',
                            label: button.label,
                            target: button.target,
                            ephemeral: button.ephemeral || false
                        };
                    } else {
                        return {
                            type: 'link',
                            label: button.label,
                            url: button.url
                        };
                    }
                }),
                selects: embed.actions.filter(action => action.type === 'select').map(select => ({
                    placeholder: select.placeholder,
                    name: select.placeholder.toLowerCase().replace(/\s+/g, '_'),
                    options: select.options.map(option => ({
                        label: option.label,
                        value: option.value,
                        description: option.description || '',
                        icon: option.icon || ''
                    }))
                }))
            })).filter(embed => Object.keys(embed).length > 0),
            // Include metadata
            metadata: {
                total_embeds: this.embeds.length,
                has_actions: this.embeds.some(embed => embed.actions.length > 0),
                has_buttons: this.embeds.some(embed => embed.actions.some(action => action.type === 'button')),
                has_selects: this.embeds.some(embed => embed.actions.some(action => action.type === 'select')),
                generated_at: new Date().toISOString(),
                version: '2.0'
            }
        };

        if (username) payload.username = username;
        if (avatar) payload.avatar_url = avatar;

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                alert('Webhook sent successfully with complete JSON data!');
                this.closeModal('webhook-modal');
            } else {
                const error = await response.text();
                alert('Failed to send webhook: ' + error);
            }
        } catch (error) {
            alert('Error sending webhook: ' + error.message);
        }
    }

    saveCurrentEmbed(embedIndex = null) {
        const index = embedIndex !== null ? embedIndex : this.currentEmbedIndex;
        const key = prompt('Enter a name for this embed:');
        if (!key) return;

        const embed = this.embeds[index];
        const data = {
            key,
            embed,
            timestamp: Date.now()
        };

        localStorage.setItem(`embed_${key}`, JSON.stringify(data));
        this.loadSavedEmbeds();
        alert(`Embed "${key}" saved!`);
    }

    loadSavedEmbeds() {
        const container = document.getElementById('saved-list');
        container.innerHTML = '';

        const savedEmbeds = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith('embed_')) {
                try {
                    const data = JSON.parse(localStorage.getItem(key));
                    savedEmbeds.push({ key: key.replace('embed_', ''), data });
                } catch (e) {
                    // Skip invalid entries
                }
            }
        }

        if (savedEmbeds.length === 0) {
            container.innerHTML = '<div class="text-muted">No saved embeds</div>';
      return;
    }

        savedEmbeds.forEach(({ key, data }) => {
            const item = document.createElement('div');
            item.className = 'saved-item';
            item.addEventListener('click', () => this.loadEmbed(data.embed));

            const name = document.createElement('div');
            name.className = 'saved-item-name';
            name.textContent = key;

            item.appendChild(name);
        container.appendChild(item);
        });
    }

    loadEmbed(embed) {
        this.embeds[this.currentEmbedIndex] = { ...embed };
        this.render();
    }

    exportJSON() {
        const data = {
            embeds: this.embeds.map(embed => ({
                title: embed.title || undefined,
                description: embed.description || undefined,
                color: embed.color ? parseInt(embed.color, 16) : undefined,
                url: embed.url || undefined,
                author: embed.author.name ? {
                    name: embed.author.name,
                    url: embed.author.url || undefined,
                    icon_url: embed.author.icon_url || undefined
                } : undefined,
                thumbnail: embed.thumbnail.url ? {
                    url: embed.thumbnail.url
                } : undefined,
                image: embed.image.url ? {
                    url: embed.image.url
                } : undefined,
                fields: embed.fields.filter(field => field.name || field.value).map(field => ({
                    name: field.name || '\u200b',
                    value: field.value || '\u200b',
                    inline: field.inline
                })),
                footer: embed.footer.text ? {
                    text: embed.footer.text,
                    icon_url: embed.footer.icon_url || undefined
                } : undefined
            })).filter(embed => Object.keys(embed).length > 0)
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'embeds.json';
        a.click();
        URL.revokeObjectURL(url);
    }

    exportCompleteJSON() {
        // Create comprehensive payload with all data including actions
        const payload = {
            embeds: this.embeds.map(embed => ({
                title: embed.title || undefined,
                description: embed.description || undefined,
                color: embed.color ? parseInt(embed.color, 16) : undefined,
                url: embed.url || undefined,
                author: embed.author.name ? {
                    name: embed.author.name,
                    url: embed.author.url || undefined,
                    icon_url: embed.author.icon_url || undefined
                } : undefined,
                thumbnail: embed.thumbnail.url ? {
                    url: embed.thumbnail.url
                } : undefined,
                image: embed.image.url ? {
                    url: embed.image.url
                } : undefined,
                fields: embed.fields.filter(field => field.name || field.value).map(field => ({
                    name: field.name || '\u200b',
                    value: field.value || '\u200b',
                    inline: field.inline
                })),
                footer: embed.footer.text ? {
                    text: embed.footer.text,
                    icon_url: embed.footer.icon_url || undefined
                } : undefined,
                // Include actions (buttons and select menus)
                buttons: embed.actions.filter(action => action.type === 'button').map(button => {
                    if (button.buttonType === 'send_embed') {
                        return {
                            type: 'send_embed',
                            label: button.label,
                            target: button.target,
                            ephemeral: button.ephemeral || false
                        };
                    } else {
                        return {
                            type: 'link',
                            label: button.label,
                            url: button.url
                        };
                    }
                }),
                selects: embed.actions.filter(action => action.type === 'select').map(select => ({
                    placeholder: select.placeholder,
                    name: select.placeholder.toLowerCase().replace(/\s+/g, '_'),
                    options: select.options.map(option => ({
                        label: option.label,
                        value: option.value,
                        description: option.description || '',
                        icon: option.icon || ''
                    }))
                }))
            })).filter(embed => Object.keys(embed).length > 0),
            // Include metadata
            metadata: {
                total_embeds: this.embeds.length,
                has_actions: this.embeds.some(embed => embed.actions.length > 0),
                has_buttons: this.embeds.some(embed => embed.actions.some(action => action.type === 'button')),
                has_selects: this.embeds.some(embed => embed.actions.some(action => action.type === 'select')),
                generated_at: new Date().toISOString(),
                version: '2.0'
            }
        };

        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `complete_embed_export_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        // Show success message
        alert('Complete JSON exported successfully! This includes all embeds, buttons, select menus, and metadata.');
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  try {
    // Ensure single initialization
    if (!window.embedBuilder) {
      window.embedBuilder = new EmbedBuilder(); // constructor calls init()
    }

    // Bind contextmenu handler once
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn && !sendBtn._ctxmenuBound) {
      sendBtn.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        // existing contextmenu handler code (if any) can go here
      });
      sendBtn._ctxmenuBound = true;
    }

  } catch (err) {
    console.error("EmbedBuilder initialization failed:", err);
  }
});