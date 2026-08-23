import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.knowtis.app',
  appName: 'Knowtis',
  webDir: 'out',
  server: {
    androidScheme: 'https',
    allowNavigation: [
      'localhost',
      '127.0.0.1',
      '10.0.2.2',
      '*.trycloudflare.com',
    ],
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: false,
      launchShowDuration: 3000,
      backgroundColor: "#FBFBFA",
      showSpinner: false,
      androidSplashResourceName: "splash",
    },
    LocalNotifications: {
      smallIcon: "ic_stat_k_outline",
      iconColor: "#FF5A36",
      sound: "beep.wav",
    },
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },
  },
};

export default config;
