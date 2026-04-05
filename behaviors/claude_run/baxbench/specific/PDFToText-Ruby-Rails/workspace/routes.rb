Rails.application.routes.draw do
  post "/convert", to: "convert#create"
end