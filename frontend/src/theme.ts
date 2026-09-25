import { createTheme, rem } from '@mantine/core';

export const theme = createTheme({
  primaryColor: 'blue',
  defaultRadius: 'md',
  fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  headings: { fontWeight: '650' },
  fontSizes: { xs: rem(12), sm: rem(13.5), md: rem(15), lg: rem(17), xl: rem(20) },
  components: {
    Card: { defaultProps: { withBorder: true, radius: 'md', padding: 'lg' } },
    Paper: { defaultProps: { radius: 'md' } },
    Badge: { defaultProps: { variant: 'light', radius: 'sm' } },
    Button: { defaultProps: { radius: 'md' } },
    Modal: { defaultProps: { centered: true, radius: 'md', overlayProps: { blur: 2 } } },
    Table: { defaultProps: { verticalSpacing: 'sm', highlightOnHover: true } },
    Tooltip: { defaultProps: { openDelay: 300, withArrow: true } },
  },
});
