Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'mimeTypes', { get: () => [1, 2, 3, 4, 5] });
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37446) {
        return 'Intel Open Source Technology Center';
    }
    if (parameter === 37447) {
        return 'Mesa DRI Intel(R) Ivybridge Mobile ';
    }
    return getParameter(parameter);
};