let cities = new Set();

// Функция для форматирования строки перед отправкой в API
function formatForApi(str) {
    return str.trim()
             .toLowerCase()
             .replace(/\s+/g, ' ');
}

// Функция для форматирования строки для отображения
function formatForDisplay(str) {
    return str.trim()
             .split(' ')
             .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
             .join(' ');
}

// Функция для получения списка городов
async function fetchCities(query) {
    try {
        const response = await fetch(`/api/search?query=${encodeURIComponent(query)}`, {
            headers: { 'Accept': 'application/json' }
        });
        const data = await response.json();
        return data.hotels.map(hotel => hotel.city);
    } catch (error) {
        console.error('Ошибка при получении городов:', error);
        return [];
    }
}

document.getElementById('searchForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const searchQuery = document.getElementById('search').value;
    const searchResults = document.getElementById('searchResults');
    
    // Разделяем ввод на страну и город, игнорируя регистр
    const parts = searchQuery.split(/\s+/).filter(Boolean);
    
    if (parts.length < 2) {
        searchResults.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-circle"></i>
                <p>Пожалуйста, введите страну и город через пробел</p>
            </div>
        `;
        return;
    }

    const country = parts[0];
    const city = parts.slice(1).join(' ');

    try {
        searchResults.innerHTML = '<div class="loading">Поиск отелей...</div>';
        
        const response = await fetch(`/api/search?country=${encodeURIComponent(country)}&city=${encodeURIComponent(city)}`, {
            headers: { 'Accept': 'application/json' }
        });
        
        const data = await response.json();
        
        if (response.status === 429) {
            throw new Error('Слишком много запросов. Пожалуйста, подождите немного и попробуйте снова.');
        }
        
        if (!response.ok) {
            throw new Error(data.message || 'Ошибка при поиске отелей');
        }
        
        if (data.hotels && data.hotels.length > 0) {
            // Используем отформатированные значения для отображения
            const displayCountry = formatForDisplay(country);
            const displayCity = formatForDisplay(city);

            // Функция для подсчета количества доступной информации об отеле
            const getInfoScore = hotel => {
                let score = 0;
                if (hotel.name) score += 1;
                if (hotel.address) score += 2;
                if (hotel.website) score += 3;
                if (hotel.booking_url) score += 2;
                if (hotel.phone && hotel.phone !== "Нет данных") score += 1;
                if (hotel.stars && hotel.stars !== "Нет данных") score += 2;
                return score;
            };

            // Сортируем отели только по количеству информации
            const sortedHotels = data.hotels.sort((a, b) => {
                const scoreA = getInfoScore(a);
                const scoreB = getInfoScore(b);
                if (scoreB !== scoreA) return scoreB - scoreA;
                
                const starsA = a.stars === "Нет данных" ? 0 : parseFloat(a.stars);
                const starsB = b.stars === "Нет данных" ? 0 : parseFloat(b.stars);
                return starsB - starsA;
            });

            // Сохраняем отели для последующей фильтрации
            window.allHotels = sortedHotels;
            
            let html = `
                <div class="results-header">
                    <h2>Отели: ${displayCountry}, ${displayCity}</h2>
                    <div class="filter-container">
                        <select id="starsFilter" class="stars-filter" onchange="filterResults()">
                            <option value="all">Все звезды</option>
                            <option value="5">5 звезд</option>
                            <option value="4">4 звезды</option>
                            <option value="3">3 звезды</option>
                            <option value="2">2 звезды</option>
                            <option value="1">1 звезда</option>
                        </select>
                    </div>
                </div>
                <p class="results-count">Найдено отелей: <span id="hotelsCount">${sortedHotels.length}</span></p>
                <ul class="hotels-list" id="hotelsList">
            `;
            
            sortedHotels.forEach(hotel => {
                if (hotel.website && hotel.address) {  // Дополнительная проверка
                    html += `
                        <li class="hotel-card">
                            <div class="hotel-info">
                                <h3>${hotel.name}</h3>
                                <p><i class="fas fa-map-marker-alt"></i> ${hotel.address}</p>
                                ${hotel.stars && hotel.stars !== "Нет данных" ? 
                                    `<p><i class="fas fa-star"></i> ${hotel.stars} звезд</p>` : ''}
                                ${hotel.phone && hotel.phone !== "Нет данных" ? 
                                    `<p><i class="fas fa-phone"></i> ${hotel.phone}</p>` : ''}
                            </div>
                            <div class="hotel-actions">
                                <a href="${hotel.website}" target="_blank" class="hotel-button" 
                                   title="Официальный сайт">
                                    <i class="fas fa-globe"></i>
                                </a>
                                ${hotel.booking_url ? `
                                    <a href="${hotel.booking_url}" target="_blank" class="hotel-button booking-button" 
                                       title="Забронировать">
                                        <i class="fas fa-bed"></i>
                                    </a>
                                ` : ''}
                            </div>
                        </li>
                    `;
                }
            });
            
            html += '</ul>';
            searchResults.innerHTML = html;
        } else {
            searchResults.innerHTML = `
                <div class="no-results">
                    <i class="fas fa-search"></i>
                    <p>Отели с подробной информацией в ${city}, ${country} не найдены</p>
                    <p>Попробуйте изменить запрос</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Ошибка при поиске:', error);
        searchResults.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-circle"></i>
                <p>${error.message}</p>
                <p>Проверьте правильность написания страны и города</p>
            </div>
        `;
    }
});

// Добавляем функцию фильтрации
function filterResults() {
    const starsFilter = document.getElementById('starsFilter').value;
    const hotelsList = document.getElementById('hotelsList');
    const hotelsCount = document.getElementById('hotelsCount');
    
    let filteredHotels = window.allHotels;
    
    if (starsFilter !== 'all') {
        filteredHotels = window.allHotels.filter(hotel => {
            const stars = parseFloat(hotel.stars);
            return !isNaN(stars) && stars === parseFloat(starsFilter);
        });
    }
    
    let html = '';
    filteredHotels.forEach(hotel => {
        if (hotel.website && hotel.address) {
            html += `
                <li class="hotel-card">
                    <div class="hotel-info">
                        <h3>${hotel.name}</h3>
                        <p><i class="fas fa-map-marker-alt"></i> ${hotel.address}</p>
                        ${hotel.stars && hotel.stars !== "Нет данных" ? 
                            `<p><i class="fas fa-star"></i> ${hotel.stars} звезд</p>` : ''}
                        ${hotel.phone && hotel.phone !== "Нет данных" ? 
                            `<p><i class="fas fa-phone"></i> ${hotel.phone}</p>` : ''}
                    </div>
                    <div class="hotel-actions">
                        <a href="${hotel.website}" target="_blank" class="hotel-button" 
                           title="Официальный сайт">
                            <i class="fas fa-globe"></i>
                        </a>
                        ${hotel.booking_url ? `
                            <a href="${hotel.booking_url}" target="_blank" class="hotel-button booking-button" 
                               title="Забронировать">
                                <i class="fas fa-bed"></i>
                            </a>
                        ` : ''}
                    </div>
                </li>
            `;
        }
    });
    
    hotelsList.innerHTML = html;
    hotelsCount.textContent = filteredHotels.length;
}
