<img src="./src/assets/yfiles-logo.svg" alt="yFiles logo" height="100"/>

# yFiles integration for create-vue

This sample application serves as a basic scaffold of how to integrate [yFiles for HTML](https://www.yfiles.com/the-yfiles-sdk/web/yfiles-for-html) in a [create-vue](https://vuejs.org/guide/quick-start.html) application.

**To run this project, a valid [yFiles for HTML](https://www.yfiles.com/the-yfiles-sdk/web/yfiles-for-html) version is required. You can evaluate yFiles 60 days free of charge on [my.yworks.com](https://my.yworks.com/signup?product=YFILES_HTML_EVAL).**

## Prerequisites

- Install [Node.js](https://nodejs.org/) (LTS version is recommended) before running any npm scripts.
- Download a matching yFiles for HTML `.tgz` archive from your yFiles installation. In the evaluation package you will find it inside the `lib/` folder (for example `lib/yfiles-30.0.3+eval-dev.tgz`). Copy that file into the project root so that it sits next to `package.json`. The dependency declaration in `package.json` expects the file at `./yfiles-30.0.3+eval-dev.tgz` – adjust the name if you are using a different yFiles build.
- Replace the placeholder `license.json` in the project root with the license file that belongs to your yFiles distribution. The post-install script copies it to `src/license.json`, so keeping it up to date here is enough.

## Version Information

- create-vue v3.3
- yFiles for HTML 3.0

## Getting Started

1. Clone this repository (or your fork):
   ```
   git clone https://github.com/<your-account>/project_rdmstokgs.git
   cd project_rdmstokgs/yfiles-vue-integration-basic-master
   ```
2. Ensure the yFiles `.tgz` archive and your `license.json` are present as described above.
3. Install dependencies:
   ```
   npm install
   ```
4. Start the dev server on [http://localhost:5173/](http://localhost:5173/):
   ```
   npm run dev
   ```

Run `npm run build` whenever you need a production build, and `npm run preview` to inspect that build locally.

## Under the Hood

This project is a basic create-vue application, where yFiles was added as an additional dependency to integrate a basic graph component.

A step-by-step description of how to integrate yFiles in a Vue application can be found [here](integration-howto.md).

## What's Next?

This basic yFiles integration can be used as a starting point to test the capabilities of yFiles or to implement your own use case. yFiles for HTML comes with a lot of [source-code demos](https://www.yfiles.com/demos) that show different aspects of the library.

You can browse through the demos and look for features that you find interesting for your use case and integrate it in this basic component to build a more sophisticated application.

The yFiles package also contains a more extensive [Vue integration demo](https://www.yfiles.com/demos/toolkit/vue/) ([GitHub](https://github.com/yWorks/yfiles-for-html-demos/blob/master/demos/toolkit/vue)), as well as a specialized [Vue.js Template Node Style](https://www.yfiles.com/demos/style/vue-template-node-style/) ([GitHub](https://github.com/yWorks/yfiles-for-html-demos/tree/master/demos/style/vue-template-node-style)) that leverages the powerful data binding and conditional rendering features of Vue.js.

Furthermore, there is an extensive [Developer's Guide](https://docs.yworks.com/yfileshtml/#/dguide/introduction#top) that covers anything from graph creation and styling to automatic layouts and advanced customizations.

## Create a Diagram Application with Vue

The [App Generator](https://www.yworks.com/products/app-generator) is a tool that lets you interactively create a diagram
application prototype to visualize your data. Select features like editing, context menu, graph search, or printing
and customize the interaction with the graph. Generate Vue code for your prototype and use it with a valid
[yFiles for HTML](https://www.yfiles.com/the-yfiles-sdk/web/yfiles-for-html) version.

## Support

If you need help with your setup or a certain feature, don't hesitate to contact our support through
the [Customer Center](https://my.yworks.com/) or by email [yfileshtml@yworks.com](mailto:yfileshtml@yworks.com).
