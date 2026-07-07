import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.knowtis.app',
  appName: 'Knowtis',
  webDir: 'out',
  server: {
    androidScheme: 'https',
    allowNavigation: [
      'knowtis-backend.onrender.com',
      'knowtis-whatsapp.onrender.com',
    ],
  },
};

export default config;
