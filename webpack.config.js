const path = require('path');

module.exports = {
  entry: './static/js/index.js',
  mode: 'development',
  output: {
    path: path.resolve(__dirname, 'static', 'dist'),
    filename: 'bundle.js',
  },

  devServer: {
    static: {
      directory: path.join(__dirname, 'static'),
    },
    hot: true,
    port: 3000,
    open: true,
  },
  module: {
    rules: [
      {
        test: /\.css$/i,
        use: ['style-loader', 'css-loader'],
      },
    ],
  },
};
