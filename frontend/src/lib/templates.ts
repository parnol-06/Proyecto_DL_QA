export interface Template {
  label: string
  story: string
  context: string
}

export const TEMPLATES: Record<string, Template> = {
  login: {
    label: 'Login with email and password',
    story: 'As a registered user I want to log in with my email and password to access my personal account.',
    context: 'The system must lock the account after 3 failed attempts and send a recovery email.',
  },
  registro: {
    label: 'New user registration',
    story: 'As a visitor I want to register on the platform by providing my name, email and password to create my account.',
    context: 'The email must be unique in the system. The password must have at least 8 characters.',
  },
  checkout: {
    label: 'Checkout process',
    story: 'As a customer I want to complete a purchase by selecting a payment method and shipping address to receive my order.',
    context: 'Integration with payment gateway. Stock must be validated before confirming the order.',
  },
  busqueda: {
    label: 'Product search',
    story: 'As a user I want to search for products by name, category or price to quickly find what I need.',
    context: 'The search engine must support combined filters and sorting by relevance, price and rating.',
  },
  upload: {
    label: 'File upload',
    story: 'As a user I want to upload documents to the system to attach them to my requests.',
    context: 'Allowed formats: PDF, DOCX, PNG, JPG. Maximum size: 10MB per file.',
  },
  recuperacion: {
    label: 'Password recovery',
    story: 'As a user who forgot their password I want to receive a recovery link in my email to restore access to my account.',
    context: 'The link must expire in 30 minutes. It can only be used once.',
  },
  perfil: {
    label: 'Edit user profile',
    story: 'As an authenticated user I want to edit my profile data (name, photo, phone) to keep my information up to date.',
    context: 'Changes must be reflected immediately in the UI without reloading the page.',
  },
  notificaciones: {
    label: 'Notification system',
    story: 'As a user I want to receive real-time notifications about the status of my orders to stay informed without checking manually.',
    context: 'Notifications must appear in the top bar and also be sent by email according to preferences.',
  },
}
