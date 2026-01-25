// Discohook-style Embed Builder with Message Support
class EmbedBuilder {
    constructor() {
        this.messages = []; // Array of messages, each containing multiple embeds
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
        document.getElementById('add-embed-to-message-btn').addEventListener('click', () => this.addEmbed());
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
                    this.saveCurrentMessage();
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
        if (currentMessage.embeds.length === 0) return;
        
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
        this.renderMessageList();
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
        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        const action = currentMessage.embeds[this.currentEmbedIndex].actions[actionIndex];
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
        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        currentMessage.embeds[this.currentEmbedIndex].actions.splice(actionIndex, 1);
        this.renderActions();
        this.renderPreview();
    }

    addActionOption(actionIndex) {
        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        const option = {
            label: '',
            value: '',
            description: '',
            icon: ''
        };

        currentMessage.embeds[this.currentEmbedIndex].actions[actionIndex].options.push(option);
        this.renderActions();
    }

    addSavedMessageOption(actionIndex, optionIndex) {
        const savedMessages = this.getSavedMessages();
        if (savedMessages.length === 0) {
            alert('No saved messages available');
            return;
        }

        // Create a modal for message selection
        this.createMessageSelectionModal(savedMessages, (selectedKey) => {
            if (!selectedKey) return;

            const selectedMessage = savedMessages.find(msg => msg.key === selectedKey);
            if (!selectedMessage) {
                alert('Message not found');
                return;
            }

            // Update the option with the saved message reference
            const currentMessage = this.messages[this.currentMessageIndex];
            currentMessage.embeds[this.currentEmbedIndex].actions[actionIndex].options[optionIndex].label = selectedKey;
            currentMessage.embeds[this.currentEmbedIndex].actions[actionIndex].options[optionIndex].value = `send:${selectedKey}`;
            currentMessage.embeds[this.currentEmbedIndex].actions[actionIndex].options[optionIndex].description = `Send saved message: ${selectedKey}`;
            
            this.renderActions();
            this.renderPreview();
        });
    }

    addSavedMessageToButton(actionIndex) {
        const savedMessages = this.getSavedMessages();
        if (savedMessages.length === 0) {
            alert('No saved messages available');
            return;
        }

        // Create a modal for message selection
        this.createMessageSelectionModal(savedMessages, (selectedKey) => {
            if (!selectedKey) return;

            const selectedMessage = savedMessages.find(msg => msg.key === selectedKey);
            if (!selectedMessage) {
                alert('Message not found');
                return;
            }

            // Update the button with the saved message reference
            const currentMessage = this.messages[this.currentMessageIndex];
            currentMessage.embeds[this.currentEmbedIndex].actions[actionIndex].target = `send:${selectedKey}`;
            this.renderActions();
            this.renderPreview();
        });
    }

    createMessageSelectionModal(savedMessages, callback) {
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
            <h2>Select Saved Message</h2>
            <button class="modal-close" id="message-selection-close">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;

        // Create body with message list
        const body = document.createElement('div');
        body.className = 'modal-body';
        body.style.maxHeight = '400px';
        body.style.overflowY = 'auto';

        const messageList = document.createElement('div');
        messageList.className = 'message-selection-list';
        messageList.style.display = 'flex';
        messageList.style.flexDirection = 'column';
        messageList.style.gap = '0.5rem';

        savedMessages.forEach(message => {
            const messageItem = document.createElement('div');
            messageItem.className = 'message-selection-item';
            messageItem.style.display = 'flex';
            messageItem.style.alignItems = 'center';
            messageItem.style.gap = '1rem';
            messageItem.style.padding = '1rem';
            messageItem.style.border = '1px solid var(--border)';
            messageItem.style.borderRadius = '8px';
            messageItem.style.cursor = 'pointer';
            messageItem.style.transition = 'all 0.2s ease';

            messageItem.addEventListener('mouseenter', () => {
                messageItem.style.background = 'var(--background-tertiary)';
                messageItem.style.borderColor = 'var(--primary)';
            });

            messageItem.addEventListener('mouseleave', () => {
                messageItem.style.background = 'transparent';
                messageItem.style.borderColor = 'var(--border)';
            });

            messageItem.addEventListener('click', () => {
                callback(message.key);
                document.body.removeChild(modal);
            });

            const messageInfo = document.createElement('div');
            messageInfo.style.flex = '1';

            const messageName = document.createElement('div');
            messageName.style.fontWeight = '600';
            messageName.style.color = 'var(--text-primary)';
            messageName.style.marginBottom = '0.25rem';
            messageName.textContent = message.key;

            const messagePreview = document.createElement('div');
            messagePreview.style.fontSize = '0.875rem';
            messagePreview.style.color = 'var(--text-secondary)';
            const firstEmbed = message.data.embeds?.[0];
            messagePreview.textContent = firstEmbed?.title || firstEmbed?.description || `${message.data.embeds?.length || 0} embeds`;

            messageInfo.appendChild(messageName);
            messageInfo.appendChild(messagePreview);
            messageItem.appendChild(messageInfo);

            messageList.appendChild(messageItem);
        });

        body.appendChild(messageList);

        // Create footer
        const footer = document.createElement('div');
        footer.className = 'modal-footer';
        footer.innerHTML = `
            <button class="btn btn-secondary" id="message-selection-cancel">Cancel</button>
        `;

        modalContent.appendChild(header);
        modalContent.appendChild(body);
        modalContent.appendChild(footer);
        modal.appendChild(modalContent);
        document.body.appendChild(modal);

        // Add event listeners
        document.getElementById('message-selection-close').addEventListener('click', () => {
            document.body.removeChild(modal);
        });

        document.getElementById('message-selection-cancel').addEventListener('click', () => {
            document.body.removeChild(modal);
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        });
    }

    getSavedMessages() {
        const savedMessages = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith('message_')) {
                try {
                    const data = JSON.parse(localStorage.getItem(key));
                    savedMessages.push({ key: key.replace('message_', ''), data });
                } catch (e) {
                    // Skip invalid entries
                }
            }
        }
        return savedMessages;
    }

    updateActionOption(actionIndex, optionIndex, property, value) {
        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        const option = currentMessage.embeds[this.currentEmbedIndex].actions[actionIndex].options[optionIndex];
        option[property] = value;
        this.renderPreview();
    }

    deleteActionOption(actionIndex, optionIndex) {
        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        currentMessage.embeds[this.currentEmbedIndex].actions[actionIndex].options.splice(optionIndex, 1);
        this.renderActions();
    }

    render() {
        this.renderMessageList();
        this.renderForm();
        this.renderPreview();
        this.updateCounter();
    }

    renderMessageList() {
        const container = document.getElementById('embed-list');
        container.innerHTML = '';

        this.messages.forEach((message, messageIndex) => {
            const messageItem = document.createElement('div');
            messageItem.className = `message-item ${messageIndex === this.currentMessageIndex ? 'active' : ''}`;
            messageItem.style.marginBottom = '1rem';
            messageItem.style.border = '1px solid var(--border)';
            messageItem.style.borderRadius = '8px';
            messageItem.style.padding = '0.75rem';

            const messageHeader = document.createElement('div');
            messageHeader.className = 'message-header';
            messageHeader.style.display = 'flex';
            messageHeader.style.alignItems = 'center';
            messageHeader.style.justifyContent = 'space-between';
            messageHeader.style.marginBottom = '0.5rem';
            messageHeader.addEventListener('click', () => this.setCurrentMessage(messageIndex));

            const messageTitle = document.createElement('div');
            messageTitle.className = 'message-title';
            messageTitle.style.fontWeight = '600';
            messageTitle.style.color = 'var(--text-primary)';
            messageTitle.textContent = `Message ${messageIndex + 1} (${message.embeds.length} embed${message.embeds.length !== 1 ? 's' : ''})`;

            const messageActions = document.createElement('div');
            messageActions.className = 'message-actions';
            messageActions.style.display = 'flex';
            messageActions.style.gap = '0.5rem';

            const addEmbedBtn = document.createElement('button');
            addEmbedBtn.className = 'btn btn-sm btn-secondary';
            addEmbedBtn.innerHTML = '+';
            addEmbedBtn.title = 'Add embed to this message';
            addEmbedBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.setCurrentMessage(messageIndex);
                this.addEmbed();
            });

            const saveBtn = document.createElement('button');
            saveBtn.className = 'btn btn-sm btn-secondary';
            saveBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17,21 17,13 7,13 7,21"></polyline><polyline points="7,3 7,8 15,8"></polyline></svg>';
            saveBtn.title = 'Save this message';
            saveBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.setCurrentMessage(messageIndex);
                this.saveCurrentMessage();
            });

            messageActions.appendChild(addEmbedBtn);
            messageActions.appendChild(saveBtn);
            messageHeader.appendChild(messageTitle);
            messageHeader.appendChild(messageActions);

            // Embed list within message
            const embedList = document.createElement('div');
            embedList.className = 'embed-list';
            embedList.style.marginLeft = '1rem';

            message.embeds.forEach((embed, embedIndex) => {
                const embedItem = document.createElement('div');
                embedItem.className = `embed-item ${messageIndex === this.currentMessageIndex && embedIndex === this.currentEmbedIndex ? 'active' : ''}`;
                embedItem.style.display = 'flex';
                embedItem.style.alignItems = 'center';
                embedItem.style.justifyContent = 'space-between';
                embedItem.style.gap = '0.75rem';
                embedItem.style.padding = '0.5rem';
                embedItem.style.borderRadius = '6px';
                embedItem.style.cursor = 'pointer';
                embedItem.style.transition = 'all 0.2s ease';
                embedItem.style.marginBottom = '0.25rem';
                embedItem.style.border = '1px solid transparent';

                embedItem.addEventListener('click', () => {
                    this.setCurrentMessage(messageIndex);
                    this.setCurrentEmbed(embedIndex);
                });

                const embedInfo = document.createElement('div');
                embedInfo.className = 'embed-info';
                embedInfo.style.display = 'flex';
                embedInfo.style.alignItems = 'center';
                embedInfo.style.gap = '0.5rem';

                const embedNumber = document.createElement('div');
                embedNumber.className = 'embed-number';
                embedNumber.style.fontSize = '0.75rem';
                embedNumber.style.fontWeight = '600';
                embedNumber.style.color = 'var(--text-secondary)';
                embedNumber.textContent = embedIndex + 1;

                const embedTitle = document.createElement('div');
                embedTitle.className = 'embed-title';
                embedTitle.style.fontSize = '0.875rem';
                embedTitle.style.color = 'var(--text-primary)';
                embedTitle.textContent = embed.title || `Embed ${embedIndex + 1}`;

                embedInfo.appendChild(embedNumber);
                embedInfo.appendChild(embedTitle);
                embedItem.appendChild(embedInfo);

                embedList.appendChild(embedItem);
            });

            messageItem.appendChild(messageHeader);
            messageItem.appendChild(embedList);
            container.appendChild(messageItem);
        });
    }

    renderForm() {
        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        const embed = currentMessage.embeds[this.currentEmbedIndex];

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

        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        const fields = currentMessage.embeds[this.currentEmbedIndex].fields;

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

        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        const actions = currentMessage.embeds[this.currentEmbedIndex].actions;

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
                    <option value="send_embed" ${action.buttonType === 'send_embed' ? 'selected' : ''}>Send Message</option>
                `;
                typeSelect.addEventListener('change', (e) => this.updateAction(actionIndex, 'buttonType', e.target.value));

                const urlInput = document.createElement('input');
                urlInput.type = 'url';
                urlInput.className = 'form-input';
                urlInput.placeholder = 'Button URL';
                urlInput.value = action.url || '';
                urlInput.style.display = action.buttonType === 'link' ? 'block' : 'none';
                urlInput.addEventListener('input', (e) => this.updateAction(actionIndex, 'url', e.target.value));

                // Message selection for send_embed type
                const messageSelect = document.createElement('div');
                messageSelect.className = 'message-select-container';
                messageSelect.style.display = action.buttonType === 'send_embed' ? 'block' : 'none';

                const messageSelectInput = document.createElement('input');
                messageSelectInput.type = 'text';
                messageSelectInput.className = 'form-input';
                messageSelectInput.placeholder = 'Saved message key or send_json:b64';
                messageSelectInput.value = action.target || '';
                messageSelectInput.addEventListener('input', (e) => this.updateAction(actionIndex, 'target', e.target.value));

                const useSavedMessageBtn = document.createElement('button');
                useSavedMessageBtn.className = 'btn btn-sm btn-primary';
                useSavedMessageBtn.textContent = 'Use Saved Message';
                useSavedMessageBtn.addEventListener('click', () => this.addSavedMessageToButton(actionIndex));

                messageSelect.appendChild(messageSelectInput);
                messageSelect.appendChild(useSavedMessageBtn);

                content.appendChild(labelInput);
                content.appendChild(typeSelect);
                content.appendChild(urlInput);
                content.appendChild(messageSelect);
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

                const addSavedMessageBtn = document.createElement('button');
                addSavedMessageBtn.className = 'btn btn-sm btn-primary';
                addSavedMessageBtn.textContent = 'Add Saved Message';
                addSavedMessageBtn.addEventListener('click', () => {
                    const optionIndex = action.options.length;
                    this.addActionOption(actionIndex);
                    this.addSavedMessageOption(actionIndex, optionIndex);
                });

                optionsHeader.appendChild(addOptionBtn);
                optionsHeader.appendChild(addSavedMessageBtn);
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

                    const descriptionInput = document.createElement('input');
                    descriptionInput.type = 'text';
                    descriptionInput.className = 'form-input';
                    descriptionInput.placeholder = 'Option description (optional)';
                    descriptionInput.value = option.description || '';
                    descriptionInput.addEventListener('input', (e) => this.updateActionOption(actionIndex, optionIndex, 'description', e.target.value));

                    const iconInput = document.createElement('input');
                    iconInput.type = 'text';
                    iconInput.className = 'form-input';
                    iconInput.placeholder = 'Emoji/icon (e.g., 🔥, ⭐, :fire:)';
                    iconInput.value = option.icon || '';
                    iconInput.addEventListener('input', (e) => this.updateActionOption(actionIndex, optionIndex, 'icon', e.target.value));

                    inputsContainer.appendChild(labelInput);
                    inputsContainer.appendChild(valueInput);
                    inputsContainer.appendChild(descriptionInput);
                    inputsContainer.appendChild(iconInput);

                    // Create buttons container
                    const buttonsContainer = document.createElement('div');
                    buttonsContainer.className = 'option-buttons';

                    const useSavedBtn = document.createElement('button');
                    useSavedBtn.className = 'btn btn-sm btn-primary';
                    useSavedBtn.textContent = 'Use Saved';
                    useSavedBtn.title = 'Use a saved message as this option';
                    useSavedBtn.addEventListener('click', () => this.addSavedMessageOption(actionIndex, optionIndex));

                    const deleteOptionBtn = document.createElement('button');
                    deleteOptionBtn.className = 'btn btn-sm btn-danger';
                    deleteOptionBtn.innerHTML = '🗑';
                    deleteOptionBtn.addEventListener('click', () => this.deleteActionOption(actionIndex, optionIndex));

                    buttonsContainer.appendChild(useSavedBtn);
                    buttonsContainer.appendChild(deleteOptionBtn);

                    // Add description if value contains message reference
                    if (option.value && (option.value.startsWith('send:') || option.value.startsWith('send_json:'))) {
                        const description = document.createElement('div');
                        description.className = 'option-description';
                        description.textContent = 'This option will send a message';
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

        if (this.messages.length === 0) return;

        const currentMessage = this.messages[this.currentMessageIndex];
        if (currentMessage.embeds.length === 0) return;

        // Show all embeds in the current message
        currentMessage.embeds.forEach((embed, index) => {
            const previewEmbed = document.createElement('div');
            previewEmbed.className = 'preview-embed';
            if (index > 0) {
                previewEmbed.style.marginTop = '1rem';
            }

            // Add author if present
            if (embed.author && embed.author.name) {
                const authorContainer = document.createElement('div');
                authorContainer.className = 'preview-author-container';
                authorContainer.style.display = 'flex';
                authorContainer.style.alignItems = 'center';
                authorContainer.style.gap = '0.5rem';
                authorContainer.style.marginBottom = '0.5rem';

                if (embed.author.icon_url) {
                    const authorIcon = document.createElement('img');
                    authorIcon.className = 'preview-author-icon';
                    authorIcon.src = embed.author.icon_url;
                    authorIcon.alt = 'Author icon';
                    authorIcon.style.width = '20px';
                    authorIcon.style.height = '20px';
                    authorIcon.style.borderRadius = '50%';
                    authorIcon.style.objectFit = 'cover';
                    authorIcon.onerror = function() {
                        this.style.display = 'none';
                    };
                    authorContainer.appendChild(authorIcon);
                }

                const authorName = document.createElement('div');
                authorName.className = 'preview-author-name';
                authorName.textContent = embed.author.name;
                authorName.style.fontWeight = '600';
                authorName.style.color = 'var(--text-primary)';
                authorContainer.appendChild(authorName);

                previewEmbed.appendChild(authorContainer);
            }

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

            // Add thumbnail if present
            if (embed.thumbnail && embed.thumbnail.url) {
                const thumbnailContainer = document.createElement('div');
                thumbnailContainer.className = 'preview-thumbnail-container';
                thumbnailContainer.style.display = 'flex';
                thumbnailContainer.style.alignItems = 'flex-start';
                thumbnailContainer.style.gap = '1rem';
                thumbnailContainer.style.marginTop = '0.5rem';

                const thumbnail = document.createElement('img');
                thumbnail.className = 'preview-thumbnail';
                thumbnail.src = embed.thumbnail.url;
                thumbnail.alt = 'Thumbnail';
                thumbnail.style.maxWidth = '80px';
                thumbnail.style.maxHeight = '80px';
                thumbnail.style.borderRadius = '4px';
                thumbnail.style.objectFit = 'cover';
                thumbnail.onerror = function() {
                    this.style.display = 'none';
                };

                thumbnailContainer.appendChild(thumbnail);
                previewEmbed.appendChild(thumbnailContainer);
            }

            // Add main image if present
            if (embed.image && embed.image.url) {
                const imageContainer = document.createElement('div');
                imageContainer.className = 'preview-image-container';
                imageContainer.style.marginTop = '0.5rem';

                const image = document.createElement('img');
                image.className = 'preview-image';
                image.src = embed.image.url;
                image.alt = 'Embed image';
                image.style.maxWidth = '100%';
                image.style.maxHeight = '300px';
                image.style.borderRadius = '4px';
                image.style.objectFit = 'contain';
                image.onerror = function() {
                    this.style.display = 'none';
                };

                imageContainer.appendChild(image);
                previewEmbed.appendChild(imageContainer);
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
        });
    }

    updateCounter() {
        const counter = document.getElementById('embed-counter');
        if (this.messages.length === 0) {
            counter.textContent = 'No messages';
            return;
        }
        
        const currentMessage = this.messages[this.currentMessageIndex];
        counter.textContent = `Message ${this.currentMessageIndex + 1} of ${this.messages.length} - Embed ${this.currentEmbedIndex + 1} of ${currentMessage.embeds.length}`;
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
            let messages = [];

            if (Array.isArray(data)) {
                // If it's an array, treat each item as a message
                messages = data.map(item => {
                    if (item.embeds) {
                        return item; // Already a message
                    } else {
                        return { embeds: [item] }; // Convert single embed to message
                    }
                });
            } else if (data.embeds && Array.isArray(data.embeds)) {
                // If it has embeds array, treat as a single message
                messages = [data];
            } else if (data.messages && Array.isArray(data.messages)) {
                // If it has messages array, use that
                messages = data.messages;
            } else {
                // Single embed object
                messages = [{ embeds: [data] }];
            }

            this.messages = messages.map(message => ({
                embeds: message.embeds.map(embed => ({
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
                }))
            }));

            this.currentMessageIndex = 0;
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
        // Collect all saved messages that are referenced
        const referencedMessages = this.collectReferencedMessages();
        
        const payload = {
            messages: this.messages.map(message => ({
                embeds: message.embeds.map(embed => ({
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
                    // Include actions (buttons and select menus) with inlined message data
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
                            
                            // If this option references a saved message, inline the message data
                            if (option.value && option.value.startsWith('send:')) {
                                const messageKey = option.value.substring(5); // Remove 'send:' prefix
                                const referencedMessage = referencedMessages[messageKey];
                                if (referencedMessage) {
                                    resolvedOption.value = `send_json:${btoa(JSON.stringify(referencedMessage))}`;
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
                }))
            })),
            // Include all referenced messages as inlined data
            referenced_messages: referencedMessages,
            // Include metadata
            metadata: {
                total_messages: this.messages.length,
                total_embeds: this.messages.reduce((sum, msg) => sum + msg.embeds.length, 0),
                has_actions: this.messages.some(msg => msg.embeds.some(embed => embed.actions.length > 0)),
                has_buttons: this.messages.some(msg => msg.embeds.some(embed => embed.actions.some(action => action.type === 'button'))),
                has_selects: this.messages.some(msg => msg.embeds.some(embed => embed.actions.some(action => action.type === 'select'))),
                generated_at: new Date().toISOString(),
                version: '3.0'
            }
        };
        
        // Debug: Log the payload
        console.log('Generated payload:', payload);
        console.log('Number of messages:', payload.messages.length);
        
        return payload;
    }

    collectReferencedMessages() {
        const referencedMessages = {};
        
        // Find all references to saved messages in select menu options
        this.messages.forEach(message => {
            message.embeds.forEach(embed => {
                embed.actions.forEach(action => {
                    if (action.type === 'select') {
                        action.options.forEach(option => {
                            if (option.value && option.value.startsWith('send:')) {
                                const messageKey = option.value.substring(5); // Remove 'send:' prefix
                                
                                // Get the saved message data from localStorage
                                const savedData = localStorage.getItem(`message_${messageKey}`);
                                if (savedData) {
                                    try {
                                        const parsed = JSON.parse(savedData);
                                        referencedMessages[messageKey] = parsed;
                                    } catch (e) {
                                        console.warn(`Failed to parse saved message ${messageKey}:`, e);
                                    }
                                }
                            }
                        });
                    }
                });
            });
        });
        
        return referencedMessages;
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
            embeds: this.messages.flatMap(message => 
                message.embeds.map(embed => ({
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
                }))
            ).filter(embed => Object.keys(embed).length > 0),
            // Include metadata
            metadata: {
                total_messages: this.messages.length,
                total_embeds: this.messages.reduce((sum, msg) => sum + msg.embeds.length, 0),
                generated_at: new Date().toISOString(),
                version: '3.0'
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

    saveCurrentMessage(messageIndex = null) {
        const index = messageIndex !== null ? messageIndex : this.currentMessageIndex;
        const key = prompt('Enter a name for this message:');
        if (!key) return;

        const message = this.messages[index];
        const data = {
            key,
            embeds: message.embeds,
            timestamp: Date.now()
        };

        localStorage.setItem(`message_${key}`, JSON.stringify(data));
        this.loadSavedMessages();
        alert(`Message "${key}" saved!`);
    }

    loadSavedMessages() {
        const container = document.getElementById('saved-list');
        container.innerHTML = '';

        const savedMessages = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith('message_')) {
                try {
                    const data = JSON.parse(localStorage.getItem(key));
                    savedMessages.push({ key: key.replace('message_', ''), data });
                } catch (e) {
                    // Skip invalid entries
                }
            }
        }

        if (savedMessages.length === 0) {
            container.innerHTML = '<div class="text-muted">No saved messages</div>';
            return;
        }

        savedMessages.forEach(({ key, data }) => {
            const item = document.createElement('div');
            item.className = 'saved-item';
            item.addEventListener('click', () => this.loadMessage(data));

            const name = document.createElement('div');
            name.className = 'saved-item-name';
            name.textContent = key;

            item.appendChild(name);
            container.appendChild(item);
        });
    }

    loadMessage(messageData) {
        this.messages[this.currentMessageIndex] = { embeds: messageData.embeds };
        this.currentEmbedIndex = 0;
        this.render();
    }

    exportJSON() {
        const data = {
            messages: this.messages.map(message => ({
                embeds: message.embeds.map(embed => ({
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
                }))
            }))
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'messages.json';
        a.click();
        URL.revokeObjectURL(url);
    }

    exportCompleteJSON() {
        // Create comprehensive payload with all data including actions
        const payload = this.buildCompletePayload();

        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `complete_message_export_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        // Show success message
        alert('Complete JSON exported successfully! This includes all messages, embeds, buttons, select menus, and metadata.');
    }
}

// Add these validation functions at the top of app.js
function validateEmbed(embed) {
    // Check required fields
    if (!embed.title && !embed.description && !embed.image?.url) {
        throw new Error("Embed must have at least a title, description, or image");
    }

    // Validate length limits
    if (embed.title && embed.title.length > 256) {
        throw new Error("Embed title must be 256 characters or less");
    }
    if (embed.description && embed.description.length > 4096) {
        throw new Error("Embed description must be 4096 characters or less"); 
    }

    // Validate fields
    if (embed.fields) {
        if (embed.fields.length > 25) {
            throw new Error("Embed can have maximum 25 fields");
        }
        
        embed.fields.forEach(field => {
            if (!field.name || !field.value) {
                throw new Error("Field must have both name and value");
            }
            if (field.name.length > 256) {
                throw new Error("Field name must be 256 characters or less");
            }
            if (field.value.length > 1024) {
                throw new Error("Field value must be 1024 characters or less");
            }
        });
    }

    // Validate footer
    if (embed.footer?.text && embed.footer.text.length > 2048) {
        throw new Error("Footer text must be 2048 characters or less");
    }

    // Validate author
    if (embed.author?.name && embed.author.name.length > 256) {
        throw new Error("Author name must be 256 characters or less");
    }

    // Validate URLs
    const urlFields = ['thumbnail', 'image'];
    urlFields.forEach(field => {
        if (embed[field]?.url && !isValidUrl(embed[field].url)) {
            throw new Error(`Invalid URL in ${field}`);
        }
    });

    return true;
}

function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch (_) {
        return false;
    }
}

function validateMessage(message) {
    if (!message.embeds || !Array.isArray(message.embeds)) {
        throw new Error("Message must have an embeds array");
    }

    if (message.embeds.length > 10) {
        throw new Error("Message can have maximum 10 embeds");
    }

    // Validate each embed
    message.embeds.forEach((embed, index) => {
        try {
            validateEmbed(embed);
        } catch (e) {
            throw new Error(`Embed ${index + 1}: ${e.message}`);
        }
    });

    return true;
}

// Modify the export/send functions to include validation:
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
