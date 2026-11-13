/**
 * Точка перелома раскладки. На десктопе лента событий — в боковой колонке со своей прокруткой,
 * на узких экранах — под карточками поездов. Должна совпадать с @media (max-width: 1100px) в App.vue.
 */
export const DESKTOP_MIN_WIDTH = 1101
export const DESKTOP_QUERY = `(min-width: ${DESKTOP_MIN_WIDTH}px)`
