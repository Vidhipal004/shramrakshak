export type Language = 'en' | 'hi'
export const copy = {
  en: {
    product: 'ShramRakshak', role: 'Contractor workspace', navOverview: 'Overview', navJobs: 'Job listings', navApplicants: 'Applicants', navAgreements: 'Agreements', navTravel: 'Before you go', navComplaints: 'Complaints', navProfile: 'Profile',
    signIn: 'Sign in', register: 'Create contractor account', email: 'Email address', password: 'Password', name: 'Full name', business: 'Business name', phone: 'Phone', city: 'City', state: 'State', continue: 'Continue', loading: 'Loading your workspace…', exitDemo: 'Exit demo',
    welcome: 'Good work starts with clear terms.', subtitle: 'Create transparent listings, confirm accepted agreements, and keep every conversation in one place.', jobs: 'Active listings', applicants: 'Applicants', openCases: 'Open complaints', createJob: 'Create listing', save: 'Save changes', cancel: 'Cancel', signOut: 'Sign out',
    search: 'Search listings', occupation: 'Occupation', skill: 'Skill', title: 'Job title', location: 'Work location', wage: 'Wage amount (₹)', period: 'Wage period', hours: 'Working hours', payment: 'Payment terms', startDate: 'Start date', description: 'Description', status: 'Status',
    viewApplicants: 'View applicants', accept: 'Accept', reject: 'Reject', createAgreement: 'Create wage agreement', respond: 'Send response', send: 'Send', reconfirm: 'Reconfirm accepted details', changed: 'Terms differ. Propose a new version and wait for worker acceptance.',
    noJobs: 'No listings yet. Create your first clear offer.', noCases: 'No complaints need your response.', noApplicants: 'No applicants for this listing yet.', noAgreements: 'Agreements appear here when an accepted applicant receives an offer.', noTravel: 'No pre-travel confirmations are waiting.',
    language: 'हिन्दी', dashboard: 'Workspace overview', trust: 'JobTrust report', insufficient: 'Insufficient verified data', terms: 'Accepted terms', pending: 'Pending', confirmed: 'Confirmed', updated: 'Updated',
  },
  hi: {
    product: 'श्रमरक्षक', role: 'ठेकेदार कार्यक्षेत्र', navOverview: 'डैशबोर्ड', navJobs: 'काम की सूची', navApplicants: 'आवेदक', navAgreements: 'वेतन समझौते', navTravel: 'काम पर जाने से पहले', navComplaints: 'शिकायतें', navProfile: 'प्रोफ़ाइल',
    signIn: 'लॉग इन करें', register: 'ठेकेदार खाता बनाएँ', email: 'ईमेल पता', password: 'पासवर्ड', name: 'पूरा नाम', business: 'व्यवसाय का नाम', phone: 'फ़ोन', city: 'शहर', state: 'राज्य', continue: 'आगे बढ़ें', loading: 'आपका कार्यक्षेत्र खुल रहा है…', exitDemo: 'डेमो से बाहर निकलें',
    welcome: 'साफ़ शर्तों से अच्छा काम शुरू होता है।', subtitle: 'पारदर्शी काम पोस्ट करें, स्वीकार किए गए समझौतों की पुष्टि करें और बातचीत को एक जगह रखें।', jobs: 'सक्रिय काम', applicants: 'आवेदक', openCases: 'खुली शिकायतें', createJob: 'काम पोस्ट करें', save: 'बदलाव सहेजें', cancel: 'रद्द करें', signOut: 'लॉग आउट',
    search: 'काम खोजें', occupation: 'काम का प्रकार', skill: 'कौशल', title: 'काम का शीर्षक', location: 'काम की जगह', wage: 'वेतन राशि (₹)', period: 'वेतन अवधि', hours: 'काम के घंटे', payment: 'भुगतान की शर्तें', startDate: 'शुरू होने की तारीख', description: 'विवरण', status: 'स्थिति',
    viewApplicants: 'आवेदक देखें', accept: 'स्वीकार करें', reject: 'मना करें', createAgreement: 'वेतन समझौता बनाएँ', respond: 'जवाब भेजें', send: 'भेजें', reconfirm: 'स्वीकार की गई शर्तें फिर से पुष्टि करें', changed: 'शर्तें अलग हैं। नया संस्करण भेजें और कर्मचारी की स्वीकृति की प्रतीक्षा करें।',
    noJobs: 'अभी कोई काम नहीं है। पहला साफ़ प्रस्ताव बनाएँ।', noCases: 'जवाब देने के लिए कोई शिकायत नहीं है।', noApplicants: 'इस काम के लिए अभी कोई आवेदक नहीं है।', noAgreements: 'स्वीकृत आवेदक को प्रस्ताव देने पर समझौते यहाँ दिखेंगे।', noTravel: 'जाने से पहले पुष्टि का कोई अनुरोध नहीं है।',
    language: 'English', dashboard: 'कार्य क्षेत्र का सार', trust: 'जॉबट्रस्ट रिपोर्ट', insufficient: 'सत्यापित जानकारी अभी कम है', terms: 'स्वीकृत शर्तें', pending: 'लंबित', confirmed: 'पुष्टि हुई', updated: 'अपडेट हुआ',
  },
} satisfies Record<Language, Record<string, string>>
