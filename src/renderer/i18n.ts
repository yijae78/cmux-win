import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from '../../resources/locales/en.json';
import ko from '../../resources/locales/ko.json';
import ja from '../../resources/locales/ja.json';

i18next.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ko: { translation: ko },
    ja: { translation: ja },
  },
  lng: 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
});

export default i18next;
